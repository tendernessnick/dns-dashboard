// 多部门页面离线/HTTP/分享版浏览器验收。只读取现有产物，不构建、不采集。
// DNS_PLAYWRIGHT_MODULE 可指定已有 playwright 包；DNS_BROWSER_EXECUTABLE 可指定 Chrome。
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.DNS_PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '..');
const dashboardDir = path.join(root, '看板');
const config = JSON.parse(fs.readFileSync(path.join(dashboardDir, '页面.json'), 'utf8'));
const views = config['页面'];
const defaultView = views.find(view => view.ID === config['默认页面']);
const marketView = views.find(view => view.ID === 'marketing');
const shareFile = '数据看板-单文件版.html';
const widths = [320, 390, 768, 1440, 1920];
assert.ok(defaultView && marketView && defaultView.ID !== marketView.ID, '页面配置必须含默认战略页和市场页');

function csvRows(filename) {
  const input = fs.readFileSync(filename, 'utf8').replace(/^\uFEFF/, '');
  const rows = [];
  let row = [], field = '', quoted = false;
  for (let i = 0; i < input.length; i++) {
    const char = input[i];
    if (char === '"') {
      if (quoted && input[i + 1] === '"') { field += '"'; i++; }
      else quoted = !quoted;
    } else if (char === ',' && !quoted) { row.push(field); field = ''; }
    else if ((char === '\r' || char === '\n') && !quoted) {
      if (char === '\r' && input[i + 1] === '\n') i++;
      row.push(field);
      if (row.some(Boolean)) rows.push(row);
      row = []; field = '';
    } else field += char;
  }
  assert.equal(quoted, false, 'CSV引号必须闭合：' + filename);
  if (field || row.length) { row.push(field); rows.push(row); }
  const header = rows.shift();
  return rows.map(values => Object.fromEntries(header.map((key, i) => [key, values[i] || ''])));
}

function manifest(directory, extension) {
  return fs.readdirSync(directory).filter(name => name.endsWith(extension)).sort().map(name => ({
    name, sha256: crypto.createHash('sha256').update(fs.readFileSync(path.join(directory, name))).digest('hex'),
  }));
}

const moduleDir = path.join(dashboardDir, '模块');
const originalModules = manifest(moduleDir, '.json');
assert.equal(originalModules.length, 98, '本次只复用现有98个模块，不新增模块');
const modules = new Map(originalModules.map(({ name }) => {
  const card = JSON.parse(fs.readFileSync(path.join(moduleDir, name), 'utf8'));
  return [card.ID || name.slice(0, -5), card];
}));
assert.equal(modules.size, originalModules.length, '模块配置ID唯一');
const fixedDir = path.join(root, '看板数据固化');
const originalCsvs = manifest(path.join(fixedDir, 'CSV数据'), '.csv');
const originalCollectors = manifest(path.join(fixedDir, '采集脚本'), '.py');
const registry = csvRows(path.join(fixedDir, '词条注册表.csv'));
const sources = csvRows(path.join(fixedDir, '溯源表.csv'));
const normalizePid = value => {
  const match = /^P?(\d+)([a-z]?)$/i.exec(String(value));
  return match ? 'P' + Number(match[1]) + match[2].toLowerCase() : null;
};
const sourceIds = new Set(sources.map(row => normalizePid(row['P号'])));
const splitKeys = value => String(value || '').split(/[;；]/).map(x => x.trim()).filter(Boolean);

function dependencies(refs) {
  const result = new Set();
  const visit = (value, key = '') => {
    if (Array.isArray(value)) return value.forEach(x => visit(x, key));
    if (value && typeof value === 'object') return Object.entries(value).forEach(([k, v]) => visit(v, k));
    if (typeof value !== 'string') return;
    if (/^P\d+[a-z]?$/i.test(value)) result.add(normalizePid(value));
    if (/图文|榜单/.test(key) && /^\d+$/.test(value)) result.add(normalizePid(value));
    if (key === '资讯键') {
      for (const row of registry) {
        if (splitKeys(row['资讯key']).some(item => splitKeys(value).includes(item))) {
          result.add(normalizePid(row['P号']));
        }
      }
    }
  };
  for (const ref of refs) visit(modules.get(ref));
  return [...result].filter(pid => sourceIds.has(pid)).sort();
}

for (const view of views) {
  assert.ok(view.ID && view['文件'] && view['布局'], '每页必须声明ID、文件和布局');
  assert.equal(path.basename(view['文件']), view['文件'], '独立HTML共置看板目录以共享媒体相对路径');
  view.layout = csvRows(path.join(dashboardDir, view['布局']));
  view.refs = view.layout.filter(row => row['类型'] === 'C').map(row => row['引用']);
  assert.equal(new Set(view.refs).size, view.refs.length, view.ID + '不能在同页重复引用同一模块');
  for (const ref of view.refs) assert.ok(modules.has(ref), view.ID + '引用不存在模块：' + ref);
  view.expectedSources = dependencies(view.refs);
  assert.ok(fs.existsSync(path.join(dashboardDir, view['文件'])), '先由生产构建器生成：' + view['文件']);
}
assert.deepEqual([...defaultView.refs].sort(), [...modules.keys()].sort(), '主看板完整保留原有98个模块');
assert.ok(marketView.refs.length > 0 && marketView.refs.length < defaultView.refs.length,
  '市场页从现有模块取子集，不复制或扩充模块');
assert.equal(new Set(views.map(view => view.ID)).size, views.length, '页面ID唯一');
assert.equal(new Set(views.map(view => view['文件'])).size, views.length, '输出文件唯一');

async function serveDashboard() {
  const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png', '.svg': 'image/svg+xml' };
  const server = http.createServer((request, response) => {
    try {
      const requestPath = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      const filename = path.resolve(dashboardDir, '.' + requestPath);
      if (filename !== dashboardDir && !filename.startsWith(dashboardDir + path.sep)) {
        response.writeHead(403).end(); return;
      }
      const file = filename === dashboardDir ? path.join(dashboardDir, defaultView['文件']) : filename;
      if (!fs.existsSync(file) || !fs.statSync(file).isFile()) { response.writeHead(404).end(); return; }
      response.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream',
        'Cache-Control': 'no-store' });
      fs.createReadStream(file).pipe(response);
    } catch { response.writeHead(400).end(); }
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  return { server, origin: 'http://127.0.0.1:' + server.address().port };
}

async function ready(scope) {
  await scope.waitForFunction(() => typeof DDATA !== 'undefined' && window.__provOK === true);
  await scope.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function payload(scope) {
  return scope.evaluate(() => {
    const reviews = {};
    if (typeof REVIEWS !== 'undefined') for (const [key, value] of Object.entries(REVIEWS)) {
      reviews[key] = { ...value, items: value.items.map(({ img, ...item }) => item) };
    }
    return JSON.stringify({ data: DDATA, news: NEWS, tops: TOPS, bind: BIND, win: WIN,
      cal: typeof CAL === 'undefined' ? {} : CAL, reviews });
  });
}

async function assertUniqueIds(scope, label) {
  const duplicates = await scope.evaluate(() => {
    const ids = [...document.querySelectorAll('[id]')].map(node => node.id).filter(Boolean);
    return [...new Set(ids.filter((id, i) => ids.indexOf(id) !== i))];
  });
  assert.deepEqual(duplicates, [], label + '存在重复DOM id');
}

async function assertView(scope, view, label) {
  await ready(scope);
  const rendered = await scope.locator('[data-mid]').evaluateAll(nodes => nodes.map(node => node.dataset.mid).sort());
  assert.deepEqual(rendered, [...view.refs].sort(), label + '模块必须逐一对应配置引用');
  await assertUniqueIds(scope, label);
  const brokenAnchors = await scope.evaluate(() => [...document.querySelectorAll('#dnav a,#provbtn')]
    .filter(node => !node.getAttribute('href')?.startsWith('#') ||
      !document.getElementById(decodeURIComponent(node.getAttribute('href').slice(1))))
    .map(node => node.getAttribute('href')));
  assert.deepEqual(brokenAnchors, [], label + '导航必须命中本页锚点');
  const pageLinks = await scope.locator('a[data-dashboard-page]').evaluateAll(nodes =>
    nodes.map(node => ({ id: node.dataset.dashboardPage, href: node.getAttribute('href') })));
  for (const target of views) {
    assert.ok(pageLinks.some(link => link.id === target.ID && link.href), label + '缺少页面入口：' + target.ID);
  }
  if (view.ID === marketView.ID) {
    const actual = await scope.evaluate(() => PROV.map(item => 'P' + Number(String(item.id).replace(/^P/, ''))).sort());
    assert.deepEqual(actual, view.expectedSources, label + '市场页PROV只包含本页模块及依赖');
  }
}

async function assertBusinessInvariants(scope, view, label) {
  const page = typeof scope.page === 'function' ? scope.page() : scope;
  await scope.locator('.pctl button[data-m="3"]').focus();
  await page.keyboard.press('Enter');
  assert.equal(await scope.evaluate(() => PSEL.months), 3, label + '周期支持键盘');
  assert.equal(await scope.locator('.pctl button[data-m="3"]').getAttribute('aria-pressed'), 'true');
  await scope.locator('.pctl button[data-all]').click();
  assert.equal(await scope.evaluate(() => PSEL), 'all');
  await scope.locator('.pctl button').first().click();
  assert.equal(await scope.evaluate(() => PSEL), null);

  for (const pid of ['P43', 'P45']) {
    if (!view.refs.some(ref => modules.get(ref)['主数据'] === pid)) continue;
    const card = scope.locator(`.card[data-k="${pid.slice(1)}"]`);
    assert.equal(await card.count(), 1, label + '预测卡唯一：' + pid);
    assert.match(await card.innerText(), /预测/);
    assert.equal(await card.getAttribute('data-change'), 'none');
    assert.equal(await card.locator('.chart,.sparkrow,.dpill').count(), 0, label + '预测不连线或相减');
  }
  for (const prefix of ['76_', '77_', '83_']) {
    const ref = view.refs.find(item => item.startsWith(prefix));
    if (!ref) continue;
    const card = scope.locator(`[data-mid="${ref}"]`);
    assert.ok(await card.locator('.chip.c-warn').count(), label + '受限模块不能伪装成已接入：' + prefix);
    assert.equal(await card.locator('.val .vnum').count(), 0, label + '受限项不能生成数值');
  }

  const buttons = scope.locator('[data-cotab]');
  const companies = view.layout.filter(row => row['类型'] === 'P').map(row => row['引用']);
  assert.equal(companies.length, 5, label + '保留五家公司面板');
  assert.equal(await buttons.count(), companies.length);
  for (const company of companies) {
    await scope.locator(`[data-cotab="${company}"]`).click();
    const visible = scope.locator('[data-copanel]:not([hidden])');
    assert.equal(await visible.count(), 1, label + '公司切换只能显示一个面板');
    assert.equal(await visible.getAttribute('data-copanel'), company);
    assert.equal(await scope.locator('[data-cotab].on').count(), 1);
    const cumulative = visible.locator('.card[data-change="none"]').first();
    assert.match(await cumulative.innerText(), /年初累计|年初至报告期累计/);
    assert.equal(await cumulative.locator('.dpill').count(), 0);
    const chart = cumulative.locator('.chart').first();
    await chart.scrollIntoViewIfNeeded();
    const box = await chart.boundingBox();
    assert.ok(box && box.width > 100 && box.height > 40, label + '切公司后图表必须重绘');
    await chart.locator('.hit').dispatchEvent('pointermove', {
      clientX: box.x + box.width * 0.7, clientY: box.y + box.height * 0.4, pointerType: 'mouse',
    });
    assert.ok(!(await chart.locator('.ctool').innerText()).includes('较前期'));
  }

  await buttons.first().click();
  const hiddenCard = scope.locator('[data-copanel][hidden] .card[data-change="none"]').first();
  const targetId = await hiddenCard.getAttribute('id');
  const targetPid = 'P' + (await hiddenCard.getAttribute('data-k')).split(/\s+/)[0];
  const targetCompany = await hiddenCard.evaluate(node => node.closest('[data-copanel]').dataset.copanel);
  assert.ok(targetId, label + '隐藏公司卡必须有可回跳ID');
  await scope.locator('#provbtn').click();
  await scope.locator(`#provRows [data-goto="${targetPid}"]`).click();
  await scope.waitForFunction(id => !document.getElementById(id).closest('[data-copanel]').hidden, targetId);
  assert.equal(await scope.locator('[data-copanel]:not([hidden])').getAttribute('data-copanel'), targetCompany,
    label + '附录回跳先激活隐藏公司');
  await assertUniqueIds(scope, label + '附录展开后');
}

async function responsive(page, scope, label, results) {
  for (const width of widths) {
    await page.setViewportSize({ width, height: 1000 });
    await scope.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const size = await scope.evaluate(() => ({ scroll: document.documentElement.scrollWidth,
      client: document.documentElement.clientWidth }));
    const topSize = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth,
      client: document.documentElement.clientWidth }));
    assert.ok(size.scroll <= size.client + 1, `${label} 内页横向溢出：${size.client}→${size.scroll}`);
    assert.ok(topSize.scroll <= topSize.client + 1, `${label} 分享壳横向溢出：${topSize.client}→${topSize.scroll}`);
    results.push({ page: label, viewport: width, document: size.scroll });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
}

async function sharedFrame(page, view) {
  const expected = [...view.refs].sort();
  const deadline = Date.now() + 15000;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const handle = await page.locator('[data-dashboard-frame]').elementHandle();
      const frame = handle && await handle.contentFrame();
      if (frame) {
        await frame.waitForFunction(refs => {
          const ids = [...document.querySelectorAll('[data-mid]')].map(node => node.dataset.mid).sort();
          return window.__provOK === true && JSON.stringify(ids) === JSON.stringify(refs);
        }, expected, { timeout: 800 });
        return frame;
      }
    } catch (error) { lastError = error; }
    await page.waitForTimeout(50);
  }
  throw new Error('分享壳未加载视图：' + view.ID + '；' + (lastError?.message || '缺少iframe'));
}

(async () => {
  const { server, origin } = await serveDashboard();
  let browser;
  const errors = [], responsesFailed = [], responsiveResults = [], payloads = new Map();
  const contexts = [];
  try {
    browser = await chromium.launch({ headless: true,
      ...(process.env.DNS_BROWSER_EXECUTABLE ? { executablePath: process.env.DNS_BROWSER_EXECUTABLE } : {}) });
    const context = async (offline = false) => {
      const ctx = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 1440, height: 1000 }, offline });
      contexts.push(ctx);
      // 禁止第三方请求；测试必须依赖本地产物，Amazon远程缩略图可以失败但不得影响文字数据。
      await ctx.route(/^https?:\/\//, route => {
        const local = route.request().url().startsWith(origin + '/');
        return local ? route.continue() : route.abort('blockedbyclient');
      });
      ctx.on('page', page => {
        page.setDefaultTimeout(15000);
        page.on('pageerror', error => errors.push(page.url() + ': ' + error.message));
        page.on('response', response => {
          if (response.url().startsWith(origin + '/') && response.status() >= 400) {
            responsesFailed.push(response.status() + ' ' + response.url());
          }
        });
      });
      return ctx;
    };

    for (const mode of ['file', 'http']) {
      const ctx = await context();
      const page = await ctx.newPage();
      const urlFor = view => mode === 'file'
        ? pathToFileURL(path.join(dashboardDir, view['文件'])).href
        : origin + '/' + encodeURIComponent(view['文件']);
      const navigate = async (from, to) => {
        await Promise.all([
          page.waitForURL(url => decodeURIComponent(url.pathname).endsWith('/' + to['文件'])),
          page.locator(`a[data-dashboard-page="${to.ID}"]`).first().click(),
        ]);
        await assertView(page, to, mode + ':' + to.ID);
      };
      await page.goto(urlFor(defaultView), { waitUntil: 'load' });
      for (const view of [defaultView, marketView]) {
        if (view !== defaultView) await navigate(defaultView, view);
        const label = mode + ':' + view.ID;
        await assertView(page, view, label);
        const scripts = await page.locator('script[src]').evaluateAll(nodes => nodes.map(node => node.src));
        assert.equal(scripts.filter(src => src.endsWith('/data.js')).length, 1, label + '只使用共享data.js');
        const currentPayload = await payload(page);
        if (payloads.has(view.ID)) assert.equal(currentPayload, payloads.get(view.ID), label + '同页数据与入口无关');
        else payloads.set(view.ID, currentPayload);
        await assertBusinessInvariants(page, view, label);
        await responsive(page, page, label, responsiveResults);
      }
      assert.equal(payloads.get(defaultView.ID), payloads.get(marketView.ID), '主看板与市场页复用同一份数据与绑定');
      // 附录链接会产生页内锚点历史；从明确的页面入口重新建立本组前进/后退路径。
      await page.goto(urlFor(defaultView), { waitUntil: 'load' });
      await assertView(page, defaultView, mode + ':历史起点');
      await navigate(defaultView, marketView);
      await page.reload({ waitUntil: 'load' });
      await assertView(page, marketView, mode + ':市场页刷新');
      await page.goBack({ waitUntil: 'load' });
      await assertView(page, defaultView, mode + ':后退战略页');
      await page.goForward({ waitUntil: 'load' });
      await assertView(page, marketView, mode + ':前进市场页');
      await navigate(marketView, defaultView);
    }

    // 分享版的父文档仅负责路由；业务全局变量必须从iframe读取。
    const offlineContext = await context(true);
    const sharedPage = await offlineContext.newPage();
    const shareUrl = pathToFileURL(path.join(dashboardDir, shareFile)).href;
    await sharedPage.goto(shareUrl + '#page=' + defaultView.ID, { waitUntil: 'load' });
    assert.equal(await sharedPage.evaluate(() => typeof DDATA), 'undefined', '分享父壳不假设拥有内页数据全局量');
    for (const view of [defaultView, marketView]) {
      if (view === marketView) {
        const frame = await sharedFrame(sharedPage, defaultView);
        await frame.locator(`a[data-dashboard-page="${view.ID}"]`).first().click();
        await sharedPage.waitForURL(url => new URLSearchParams(url.hash.slice(1)).get('page') === view.ID);
      }
      const frame = await sharedFrame(sharedPage, view);
      const label = 'offline-share:' + view.ID;
      await assertView(frame, view, label);
      assert.equal(await payload(frame), payloads.get(view.ID), label + '内联后业务数据保持一致');
      assert.equal(await sharedPage.locator('[data-dashboard-frame]').count(), 1, label + '保留唯一分享iframe');
      assert.ok(decodeURIComponent(new URL(sharedPage.url()).pathname).endsWith('/' + shareFile), '内页导航不能离开分享壳');
      await assertBusinessInvariants(frame, view, label);
      await responsive(sharedPage, frame, label, responsiveResults);
      // 只检查本地图文媒体；榜单第三方图片是可失效的增强信息。
      for (const image of await frame.locator('.rthumb[src]').all()) {
        await image.scrollIntoViewIfNeeded();
        await image.evaluate(node => node.decode());
        assert.ok(await image.evaluate(node => node.complete && node.naturalWidth > 0), label + '分享图文照片必须离线可见');
        assert.match(await image.getAttribute('src'), /^data:image\//, label + '图文不依赖外置媒体目录');
      }
    }
    // 排除前面附录在iframe内产生的锚点历史，只测试部门路由本身的浏览器历史。
    await sharedPage.goto(shareUrl + '#page=' + defaultView.ID, { waitUntil: 'load' });
    const historyStart = await sharedFrame(sharedPage, defaultView);
    await historyStart.locator(`a[data-dashboard-page="${marketView.ID}"]`).first().click();
    await sharedFrame(sharedPage, marketView);
    await sharedPage.reload({ waitUntil: 'load' });
    await assertView(await sharedFrame(sharedPage, marketView), marketView, 'offline-share:刷新保留市场页');
    await sharedPage.goBack({ waitUntil: 'load' });
    await assertView(await sharedFrame(sharedPage, defaultView), defaultView, 'offline-share:后退战略页');
    await sharedPage.goForward({ waitUntil: 'load' });
    await assertView(await sharedFrame(sharedPage, marketView), marketView, 'offline-share:前进市场页');
    const finalFrame = await sharedFrame(sharedPage, marketView);
    await finalFrame.locator(`a[data-dashboard-page="${defaultView.ID}"]`).first().click();
    await assertView(await sharedFrame(sharedPage, defaultView), defaultView, 'offline-share:内页返回战略');
    assert.equal(await sharedPage.locator('[data-dashboard-frame]').count(), 1);

    assert.deepEqual(manifest(moduleDir, '.json'), originalModules, '所有模块文件清单与哈希保持不变');
    assert.deepEqual(manifest(path.join(fixedDir, 'CSV数据'), '.csv'), originalCsvs, '切页面不新增或改写CSV');
    assert.deepEqual(manifest(path.join(fixedDir, '采集脚本'), '.py'), originalCollectors, '切页面不新增或改写采集器');
    assert.deepEqual(responsesFailed, [], '本地HTTP资源全部正常');
    assert.deepEqual(errors, [], '各页/iframe/切换流程零JS异常');
    console.log(JSON.stringify({ result: 'PASS', modules: originalModules.length,
      pages: views.map(view => ({ id: view.ID, modules: view.refs.length })),
      regularModes: ['file', 'http'], offlineSharing: true, companies: 5,
      browserHistory: true, duplicateIds: 0, pageErrors: errors.length,
      responsive: responsiveResults }));
  } finally {
    for (const ctx of contexts) await ctx.close();
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
