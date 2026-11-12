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
const orderedViews = [defaultView, ...views.filter(view => view !== defaultView)];
const expectedPageIds = ['strategy', 'marketing', 'design', 'product', 'hr'];
const shareFile = '数据看板-单文件版.html';
const widths = [320, 390, 768, 1440, 1920];
assert.ok(defaultView && marketView && defaultView.ID !== marketView.ID, '页面配置必须含默认战略页和市场页');
assert.deepEqual(views.map(view => view.ID).sort(), [...expectedPageIds].sort(), '五部门入口必须完整登记');

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
const modules = new Map(originalModules.map(({ name }) => {
  const card = JSON.parse(fs.readFileSync(path.join(moduleDir, name), 'utf8'));
  return [card.ID || name.slice(0, -5), card];
}));
assert.equal(modules.size, originalModules.length, '模块配置ID唯一');
const plannedModules = new Map([...modules].filter(([, card]) => card['类型'] === 'planned'));
const activeModules = new Map([...modules].filter(([, card]) => card['类型'] !== 'planned'));
assert.equal(activeModules.size, 98, '原有98个真实模块完整保留');
assert.equal(plannedModules.size, 11, '新增11个规划卡，不伪装成真实数据模块');
assert.deepEqual([...plannedModules.values()].map(card => card['预留编号']).sort(),
  Array.from({ length: 11 }, (_, i) => 'P' + (301 + i)).sort(), '沿用P号编号，仍保持规划状态');
for (const [id, card] of plannedModules) {
  assert.equal(card['预留编号'].slice(1), id.split('_')[0], '规划编号与模块ID一致');
  assert.ok(!card['主数据'] && !(card['关联数据'] || []).length, id + '预留P号不能充当真实数据绑定');
}
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
const registeredIds = new Set(registry.map(row => normalizePid(row['P号'])));
for (const [id, card] of plannedModules) {
  assert.ok(!sourceIds.has(card['预留编号']) && !registeredIds.has(card['预留编号']),
    id + '预留P号不能冒充已登记数据源或溯源词条');
}
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
  for (const ref of refs) {
    const card = modules.get(ref);
    if (card['类型'] !== 'planned') visit(card);
  }
  return [...result].filter(pid => sourceIds.has(pid)).sort();
}

for (const view of views) {
  assert.ok(view.ID && view['文件'] && view['布局'], '每页必须声明ID、文件和布局');
  assert.equal(path.basename(view['文件']), view['文件'], '独立HTML共置看板目录以共享媒体相对路径');
  view.layout = csvRows(path.join(dashboardDir, view['布局']));
  view.refs = view.layout.filter(row => row['类型'] === 'C').map(row => row['引用']);
  assert.equal(new Set(view.refs).size, view.refs.length, view.ID + '不能在同页重复引用同一模块');
  for (const ref of view.refs) assert.ok(modules.has(ref), view.ID + '引用不存在模块：' + ref);
  view.activeRefs = view.refs.filter(ref => activeModules.has(ref));
  view.plannedRefs = view.refs.filter(ref => plannedModules.has(ref));
  view.companies = view.layout.filter(row => row['类型'] === 'P').map(row => row['引用']);
  assert.equal(new Set(view.companies).size, view.companies.length, view.ID + '公司面板不重复');
  view.expectedSources = (view['完整溯源'] ?? (view.ID === defaultView.ID))
    ? [...sourceIds].sort() : dependencies(view.refs);
  assert.ok(fs.existsSync(path.join(dashboardDir, view['文件'])), '先由生产构建器生成：' + view['文件']);
}
assert.deepEqual([...defaultView.activeRefs].sort(), [...activeModules.keys()].sort(), '主看板完整保留原有98个真实模块');
assert.deepEqual(defaultView.plannedRefs.map(ref => modules.get(ref)['预留编号']).sort(), ['P301', 'P302', 'P303']);
assert.equal(marketView.activeRefs.length, 51, '市场页保留原有51个真实模块');
assert.deepEqual(marketView.plannedRefs.map(ref => modules.get(ref)['预留编号']).sort(), ['P304', 'P308']);
assert.deepEqual([...new Set(views.flatMap(view => view.plannedRefs))].sort(), [...plannedModules.keys()].sort(),
  '11个规划卡都应出现在已登记页面中');
for (const ref of plannedModules.keys()) assert.deepEqual(dependencies([ref]), [], ref + '不得生成假溯源依赖');
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

async function assertPlannedCards(scope, view, label) {
  const cards = scope.locator('.planned-card[data-module-status="planned"]');
  assert.equal(await cards.count(), view.plannedRefs.length, label + '规划卡数量与布局一致');
  for (const ref of view.plannedRefs) {
    const expected = modules.get(ref)['预留编号'];
    const card = scope.locator(`[data-mid="${ref}"]`);
    assert.equal(await card.count(), 1, label + '规划卡必须唯一：' + ref);
    assert.equal(await card.getAttribute('data-module-status'), 'planned');
    assert.equal(await card.getAttribute('data-planned-id'), expected);
    assert.ok((await card.getAttribute('class')).split(/\s+/).includes('planned-card'));
    assert.equal(await card.locator('.chip.c-planned').count(), 1);
    assert.equal((await card.locator('.chip.c-planned').innerText()).trim(), '规划中');
    const violations = await card.evaluate(root => {
      const forbidden = ['data-k', 'data-source-pids', 'data-news', 'data-review', 'data-toplist',
        'data-topsub', 'data-ring', 'data-multi', 'data-cal', 'data-cal-desc', 'data-vk', 'data-tk', 'data-ref'];
      return [root, ...root.querySelectorAll('*')].flatMap(node => forbidden
        .filter(name => node.hasAttribute(name)).map(name => node.tagName + ':' + name));
    });
    assert.deepEqual(violations, [], label + '规划卡不能绑定数据或来源：' + ref);
    assert.equal(await card.locator('.val,.vnum,.chart,.sparkrow,.dpill,.statline,.revcards,.src-ref,' +
      '.chip.c-ok,.chip.c-warn,script,iframe,object,embed,canvas').count(), 0,
    label + '规划卡不能渲染假值、趋势或已接入状态：' + ref);
    const boundary = modules.get(ref)['规划对象']['使用边界'];
    assert.ok((await card.textContent()).includes(boundary), label + '规划卡保留使用边界（可置于展开详情）');
  }
  const falseSources = await scope.evaluate(ids => {
    const stores = { DDATA, BIND, META, NEWS, TOPS,
      CAL: typeof CAL === 'undefined' ? {} : CAL,
      REVIEWS: typeof REVIEWS === 'undefined' ? {} : REVIEWS };
    return ids.flatMap(pid => [
      ...Object.entries(stores).filter(([, store]) => Object.hasOwn(store, pid)).map(([name]) => name + ':' + pid),
      ...(PROV.some(item => String(item.id).replace(/^P/i, '') === pid.slice(1)) ? ['PROV:' + pid] : []),
    ]);
  }, [...plannedModules.values()].map(card => card['预留编号']));
  assert.deepEqual(falseSources, [], label + '预留P号仅作规划标识，不能产生数据、绑定或PROV行');
}

async function assertView(scope, view, label) {
  await ready(scope);
  const rendered = await scope.locator('[data-mid]').evaluateAll(nodes => nodes.map(node => node.dataset.mid).sort());
  assert.deepEqual(rendered, [...view.refs].sort(), label + '模块必须逐一对应配置引用');
  const info = await scope.evaluate(() => PAGE_INFO);
  assert.equal(info.id, view.ID, label + '页面身份与路由一致');
  assert.equal(info.moduleCount, view.refs.length);
  assert.equal(info.activeModuleCount, view.activeRefs.length);
  assert.equal(info.plannedCount, view.plannedRefs.length);
  await assertPlannedCards(scope, view, label);
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
  const actual = await scope.evaluate(() => PROV.map(item => String(item.id)));
  assert.deepEqual(actual.map(normalizePid).sort(), view.expectedSources, label + 'PROV按本页模块和依赖过滤');
}

async function assertBusinessInvariants(scope, view, label) {
  const page = typeof scope.page === 'function' ? scope.page() : scope;
  const planDetails = scope.locator('.planned-card details').first();
  if (await planDetails.count()) {
    await planDetails.locator('summary').focus();
    await page.keyboard.press('Enter');
    assert.equal(await planDetails.evaluate(node => node.open), true, label + '规划说明支持键盘展开');
    assert.ok((await planDetails.innerText()).includes('使用边界'));
    await page.keyboard.press('Enter');
    assert.equal(await planDetails.evaluate(node => node.open), false);
  }
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

  for (const pid of ['P17', 'P18']) {
    const ref = view.activeRefs.find(item => modules.get(item)['主数据'] === pid);
    if (!ref) continue;
    const card = scope.locator(`[data-mid="${ref}"]`);
    assert.equal(await card.locator('.chip').filter({ hasText: '静态维护' }).count(), 1,
      label + '静态政策入口应明确维护状态：' + pid);
    assert.equal(await card.locator('.chip').filter({ hasText: '已接入' }).count(), 0);
    await scope.locator('#provbtn').click();
    const status = await scope.locator(`#prov-${pid} .pchip`).innerText();
    assert.equal(status.trim(), '静态维护', label + '附录不把静态入口当作持续接入');
    assert.ok(!status.includes('已接入'));
  }
  for (const prefix of ['66_', '68_']) {
    const ref = view.activeRefs.find(item => item.startsWith(prefix));
    if (!ref) continue;
    const title = await scope.locator(`[data-mid="${ref}"] .card-top .t`).innerText();
    assert.ok(!title.includes('销量'), label + 'Amazon排名不能标作销量：' + title);
    if (prefix === '68_') {
      const stats = await scope.locator(`[data-mid="${ref}"] [data-topsub]`).innerText();
      assert.ok(stats.includes('手机配件榜') && !stats.includes('充电榜'),
        label + '榜单副标题与手机配件大类口径一致');
    }
  }
  const customer = view.activeRefs.find(item => item.startsWith('80_'));
  if (customer) assert.ok(!(await scope.locator(`[data-mid="${customer}"]`).innerText()).includes('议价健康'),
    label + '大客户集中度不能冒充议价健康结论');
  assert.equal(await scope.getByText('暂无新稿', { exact: false }).count(), 0,
    label + '空feed不能擅自推断源站没有新稿');

  const buttons = scope.locator('[data-cotab]');
  const companies = view.companies;
  assert.equal(await buttons.count(), companies.length);
  assert.equal(await scope.locator('[data-copanel]').count(), companies.length);
  if (!companies.length) return;
  for (const company of companies) {
    await scope.locator(`[data-cotab="${company}"]`).click();
    const visible = scope.locator('[data-copanel]:not([hidden])');
    assert.equal(await visible.count(), 1, label + '公司切换只能显示一个面板');
    assert.equal(await visible.getAttribute('data-copanel'), company);
    assert.equal(await scope.locator('[data-cotab].on').count(), 1);
    const cumulativeRef = view.activeRefs.find(ref => {
      const card = modules.get(ref);
      return card['面板'] === company && /^P20[1-5]$/.test(card['主数据'] || '');
    });
    if (!cumulativeRef) continue;
    const cumulative = visible.locator(`[data-mid="${cumulativeRef}"]`);
    assert.equal(await cumulative.count(), 1, label + '已配置的累计营收卡必须保留');
    assert.equal(await cumulative.getAttribute('data-change'), 'none');
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
  if (!(await hiddenCard.count())) return;
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
      let previousView = defaultView;
      for (const view of orderedViews) {
        if (view !== previousView) await navigate(previousView, view);
        const label = mode + ':' + view.ID;
        await assertView(page, view, label);
        const scripts = await page.locator('script[src]').evaluateAll(nodes => nodes.map(node => node.src));
        assert.equal(scripts.filter(src => src.endsWith('/data.js')).length, 1, label + '只使用共享data.js');
        const currentPayload = await payload(page);
        if (payloads.has(view.ID)) assert.equal(currentPayload, payloads.get(view.ID), label + '同页数据与入口无关');
        else payloads.set(view.ID, currentPayload);
        await assertBusinessInvariants(page, view, label);
        await responsive(page, page, label, responsiveResults);
        previousView = view;
      }
      for (const view of views) assert.equal(payloads.get(defaultView.ID), payloads.get(view.ID),
        view.ID + '复用同一份业务数据与绑定');
      // 附录链接会产生页内锚点历史；从明确的页面入口重新建立本组前进/后退路径。
      await page.goto(urlFor(defaultView), { waitUntil: 'load' });
      await assertView(page, defaultView, mode + ':历史起点');
      const historyView = orderedViews.at(-1);
      await navigate(defaultView, historyView);
      await page.reload({ waitUntil: 'load' });
      await assertView(page, historyView, mode + ':新增部门刷新');
      await page.goBack({ waitUntil: 'load' });
      await assertView(page, defaultView, mode + ':后退战略页');
      await page.goForward({ waitUntil: 'load' });
      await assertView(page, historyView, mode + ':前进新增部门');
      await navigate(historyView, defaultView);
    }

    // 分享版的父文档仅负责路由；业务全局变量必须从iframe读取。
    const offlineContext = await context(true);
    const sharedPage = await offlineContext.newPage();
    const shareUrl = pathToFileURL(path.join(dashboardDir, shareFile)).href;
    await sharedPage.goto(shareUrl + '#page=' + defaultView.ID, { waitUntil: 'load' });
    assert.equal(await sharedPage.evaluate(() => typeof DDATA), 'undefined', '分享父壳不假设拥有内页数据全局量');
    let previousSharedView = defaultView;
    for (const view of orderedViews) {
      if (view !== previousSharedView) {
        const frame = await sharedFrame(sharedPage, previousSharedView);
        await frame.locator(`a[data-dashboard-page="${view.ID}"]`).first().click();
        await sharedPage.waitForURL(url => new URLSearchParams(url.hash.slice(1)).get('page') === view.ID);
      }
      const frame = await sharedFrame(sharedPage, view);
      const label = 'offline-share:' + view.ID;
      await assertView(frame, view, label);
      assert.equal(await frame.locator('script[src]').count(), 0, label + '离线分享不依赖外置脚本');
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
      previousSharedView = view;
    }
    // 排除前面附录在iframe内产生的锚点历史，只测试部门路由本身的浏览器历史。
    await sharedPage.goto(shareUrl + '#page=' + defaultView.ID, { waitUntil: 'load' });
    const historyStart = await sharedFrame(sharedPage, defaultView);
    const sharedHistoryView = orderedViews.at(-1);
    await historyStart.locator(`a[data-dashboard-page="${sharedHistoryView.ID}"]`).first().click();
    await sharedFrame(sharedPage, sharedHistoryView);
    await sharedPage.reload({ waitUntil: 'load' });
    await assertView(await sharedFrame(sharedPage, sharedHistoryView), sharedHistoryView, 'offline-share:刷新保留新增部门');
    await sharedPage.goBack({ waitUntil: 'load' });
    await assertView(await sharedFrame(sharedPage, defaultView), defaultView, 'offline-share:后退战略页');
    await sharedPage.goForward({ waitUntil: 'load' });
    await assertView(await sharedFrame(sharedPage, sharedHistoryView), sharedHistoryView, 'offline-share:前进新增部门');
    const finalFrame = await sharedFrame(sharedPage, sharedHistoryView);
    await finalFrame.locator(`a[data-dashboard-page="${defaultView.ID}"]`).first().click();
    await assertView(await sharedFrame(sharedPage, defaultView), defaultView, 'offline-share:内页返回战略');
    assert.equal(await sharedPage.locator('[data-dashboard-frame]').count(), 1);
    for (const invalid of ['__proto__', 'https://example.invalid/', 'unregistered']) {
      await sharedPage.goto(shareUrl + '#page=' + encodeURIComponent(invalid), { waitUntil: 'load' });
      await assertView(await sharedFrame(sharedPage, defaultView), defaultView, 'offline-share:未知部门回退');
    }

    assert.deepEqual(manifest(moduleDir, '.json'), originalModules, '所有模块文件清单与哈希保持不变');
    assert.deepEqual(manifest(path.join(fixedDir, 'CSV数据'), '.csv'), originalCsvs, '切页面不新增或改写CSV');
    assert.deepEqual(manifest(path.join(fixedDir, '采集脚本'), '.py'), originalCollectors, '切页面不新增或改写采集器');
    assert.deepEqual(responsesFailed, [], '本地HTTP资源全部正常');
    assert.deepEqual(errors, [], '各页/iframe/切换流程零JS异常');
    console.log(JSON.stringify({ result: 'PASS', modules: originalModules.length,
      pages: views.map(view => ({ id: view.ID, modules: view.refs.length,
        active: view.activeRefs.length, planned: view.plannedRefs.length, companies: view.companies.length })),
      regularModes: ['file', 'http'], offlineSharing: true, plannedModules: plannedModules.size,
      browserHistory: true, duplicateIds: 0, pageErrors: errors.length,
      responsive: responsiveResults }));
  } finally {
    for (const ctx of contexts) await ctx.close();
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
