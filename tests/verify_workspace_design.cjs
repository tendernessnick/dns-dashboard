// 工作台搜索与响应式布局回归；读取已构建产物，不构建、不采集、不改业务文件。
// DNS_PLAYWRIGHT_MODULE 指向已有Playwright包，DNS_BROWSER_EXECUTABLE 可指定Chrome。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.DNS_PLAYWRIGHT_MODULE || 'playwright');

const directory = path.resolve(__dirname, '../看板');
const config = JSON.parse(fs.readFileSync(path.join(directory, '页面.json'), 'utf8').replace(/^\uFEFF/, ''));
const views = config['页面'];
const widths = [320, 390, 768, 1440, 1920];
const shareFilename = '数据看板-单文件版.html';

async function settle(scope) {
  await scope.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function ready(scope, id) {
  await scope.waitForFunction(expected => typeof PAGE_INFO !== 'undefined' && PAGE_INFO.id === expected &&
    window.__provOK === true && document.getElementById('moduleSearch')?.dataset.workspaceSearchReady === 'true', id);
  await settle(scope);
}

async function shareFrame(page, id) {
  const deadline = Date.now() + 15000;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const handle = await page.locator('[data-dashboard-frame]').elementHandle();
      const frame = handle && await handle.contentFrame();
      if (frame) {
        await frame.waitForFunction(expected => typeof PAGE_INFO !== 'undefined' && PAGE_INFO.id === expected &&
          document.getElementById('moduleSearch')?.dataset.workspaceSearchReady === 'true', id, { timeout: 600 });
        await ready(frame, id);
        return frame;
      }
    } catch (error) { lastError = error; }
    await page.waitForTimeout(40);
  }
  throw new Error('分享壳未加载工作台：' + id + '；' + (lastError?.message || '缺少iframe'));
}

async function businessPayload(scope) {
  return scope.evaluate(() => JSON.stringify({ data: DDATA, bind: BIND, news: NEWS, tops: TOPS,
    cal: typeof CAL === 'undefined' ? {} : CAL, meta: META,
    reviews: typeof REVIEWS === 'undefined' ? {} : REVIEWS }));
}

async function visibility(scope) {
  return scope.evaluate(() => [...document.querySelectorAll('[data-mid]')].map(node => ({
    module: node.dataset.mid, hidden: node.hidden, display: node.style.display,
    panel: node.closest('[data-copanel]')?.getAttribute('data-copanel') || '',
    panelHidden: node.closest('[data-copanel]')?.hidden || false,
  })));
}

async function indexEntries(scope) {
  return scope.evaluate(() => [...document.querySelectorAll('[data-mid]')].map(node => ({
    id: node.id, module: node.dataset.mid,
    planned: node.dataset.moduleStatus === 'planned',
    title: (node.querySelector('.card-top .t,.cn')?.textContent || '').trim(),
    section: (node.closest('.mod')?.querySelector('.sec-head h2')?.textContent || '').trim(),
    pids: [...new Set([node.dataset.plannedId || '', ...(node.dataset.sourcePids || '').split(/\s+/),
      ...(node.dataset.k || '').split(/\s+/).filter(Boolean).map(value => 'P' + value)].filter(Boolean))],
    hiddenCompany: !!node.closest('[data-copanel][hidden]'),
    company: node.closest('[data-copanel]')?.getAttribute('data-copanel') || '',
  })));
}

async function search(scope, query, label, expectedModule) {
  const input = scope.locator('#moduleSearch');
  await input.fill(query);
  const panel = scope.locator('#moduleSearchResults');
  await scope.waitForFunction(() => document.getElementById('moduleSearchResults').hasAttribute('data-match-count'));
  await settle(scope);
  assert.equal(await panel.getAttribute('role'), 'status', label + '结果用status区域反馈');
  assert.equal(await panel.evaluate(node => node.hidden), false, label + '非空查询必须反馈结果');
  const buttons = panel.locator('button');
  const count = await buttons.count();
  const total = Number(await panel.getAttribute('data-match-count'));
  assert.ok(Number.isInteger(total) && total >= 0, label + '总匹配数有效');
  assert.ok(count <= 8, label + '最多展示8个结果');
  assert.equal(count, Math.min(total, 8), label + '匹配数量与可见结果一致');
  for (const button of await buttons.all()) {
    assert.ok(await button.getAttribute('data-module-id'), label + '结果保留原模块ID');
    const target = await button.getAttribute('data-workspace-target');
    assert.ok(target && await scope.evaluate(id => !!document.getElementById(id), target), label + '结果指向本页现有模块');
    assert.ok((await button.innerText()).trim(), label + '结果有可读名称');
  }
  if (expectedModule) assert.equal(await panel.locator(`button[data-module-id="${expectedModule}"]`).count(), 1,
    label + '应该找到目标模块：' + expectedModule);
  return { total, count };
}

async function clearSearch(scope, page, method, label) {
  if (method === 'escape') {
    await scope.locator('#moduleSearch').focus();
    await page.keyboard.press('Escape');
  } else await scope.locator('#clearModuleSearch').click();
  await settle(scope);
  assert.equal(await scope.locator('#moduleSearch').inputValue(), '', label + '清空查询');
  assert.equal(await scope.locator('#moduleSearchResults').evaluate(node => node.hidden), true, label + '空查询收起结果');
  assert.equal(await scope.locator('#moduleSearchResults button').count(), 0);
  assert.equal(await scope.locator('.workspace-highlight').count(), 0, label + '清空后移除旧定位高亮');
}

async function assertSearch(scope, page, view, label) {
  await ready(scope, view.ID);
  assert.equal(await scope.locator('#moduleSearch').count(), 1);
  assert.equal(await scope.locator('#clearModuleSearch').count(), 1);
  assert.equal(await scope.locator('#workspaceOverview').count(), 1);
  assert.ok((await scope.locator('#workspaceOverview').innerText()).trim(), label + '工作台概览不能空白');
  const overview = await scope.evaluate(() => ({
    expected: { '来源词条': PAGE_INFO.sourceCount, '已建模块': PAGE_INFO.activeModuleCount,
      '规划预留': PAGE_INFO.plannedCount },
    shown: Object.fromEntries([...document.querySelectorAll('#workspaceOverview .workspace-metric')]
      .map(node => [node.querySelector('span').textContent.trim(), Number(node.querySelector('b').textContent)])),
  }));
  assert.deepEqual(overview.shown, overview.expected, label + '概览分别显示来源/已建/规划，不能混淆统计范围');
  const countErrors = await scope.evaluate(() => [...document.querySelectorAll('#dnav a')].flatMap(link => {
    const section = document.getElementById((link.getAttribute('href') || '').slice(1));
    const expected = section?.querySelectorAll('[data-mid]').length;
    const count = link.querySelector('.nav-count');
    return !count || Number(count.textContent) !== expected ? [link.getAttribute('href')] : [];
  }));
  assert.deepEqual(countErrors, [], label + '目录模块数包含本板块公司面板及规划卡');
  const inputLabel = await scope.locator('#moduleSearch').evaluate(node => {
    return node.getAttribute('aria-label') || node.labels?.[0]?.textContent || '';
  });
  assert.ok(inputLabel.trim(), label + '搜索框有可访问名称');
  const entries = await indexEntries(scope);
  assert.ok(entries.length > 0 && entries.every(entry => entry.id && entry.module), label + '索引对应真实模块实例');
  const beforeVisibility = await visibility(scope);
  const beforePayload = await businessPayload(scope);
  const candidate = entries.find(entry => entry.title && !entry.hiddenCompany) || entries[0];
  const unchanged = async text => assert.deepEqual(await visibility(scope), beforeVisibility,
    label + '搜索只列结果，不能过滤或改变模块显隐：' + text);

  await search(scope, candidate.title, label + ':名称', candidate.module);
  await unchanged('名称');
  await clearSearch(scope, page, 'button', label);
  await search(scope, candidate.module, label + ':模块ID', candidate.module);
  await unchanged('模块ID');
  await clearSearch(scope, page, 'escape', label);
  const withPid = entries.find(entry => entry.pids.length && !entry.hiddenCompany) || entries.find(entry => entry.pids.length);
  assert.ok(withPid, label + '具有可检索P号');
  await search(scope, withPid.pids[0].toLowerCase(), label + ':P号忽略大小写', withPid.module);
  await unchanged('P号');
  await clearSearch(scope, page, 'button', label);
  const questionCard = entries.find(entry => entry.module.startsWith('241_'));
  if (questionCard) {
    await search(scope, 'P241', label + ':模块数字不冒充数据P号');
    assert.equal(await scope.locator(`#moduleSearchResults button[data-module-id="${questionCard.module}"]`).count(), 0,
      label + '241问答模块不是数据P241');
    await clearSearch(scope, page, 'button', label);
    await search(scope, questionCard.module, label + ':问答原模块ID', questionCard.module);
    await clearSearch(scope, page, 'button', label);
    await search(scope, 'P96', label + ':问答真实来源', questionCard.module);
    const meta = await scope.locator(`#moduleSearchResults button[data-module-id="${questionCard.module}"] .workspace-result-meta`).innerText();
    assert.ok(meta.includes('P96') && !meta.includes('P241'), label + '结果元信息保留真实来源P96');
    await unchanged('问答模块号与真实来源');
    await clearSearch(scope, page, 'button', label);
  }
  const planned = entries.find(entry => entry.planned);
  if (planned) {
    await search(scope, planned.pids[0], label + ':规划P号', planned.module);
    await unchanged('规划P号');
    await clearSearch(scope, page, 'button', label);
  }
  assert.ok(candidate.section, label + '索引包含所属板块');
  const bySection = await search(scope, candidate.section, label + ':板块');
  assert.ok(bySection.total > 0, label + '按板块检索有结果');
  await unchanged('板块');
  await clearSearch(scope, page, 'button', label);
  const sections = entries.reduce((groups, entry) => {
    if (entry.section) groups.set(entry.section, (groups.get(entry.section) || 0) + 1);
    return groups;
  }, new Map());
  const [largestSection, sectionCount] = [...sections].sort((a, b) => b[1] - a[1])[0];
  const broad = await search(scope, largestSection, label + ':结果上限');
  if (sectionCount > 8) assert.equal(broad.count, 8, label + '宽泛查询只显示前8项');
  await unchanged('宽泛查询');
  await clearSearch(scope, page, 'button', label);

  const none = await search(scope, '__workspace_no_such_module__', label + ':无匹配');
  assert.equal(none.total, 0);
  assert.match(await scope.locator('#moduleSearchResults').innerText(), /无|未|0|没有/, label + '无结果也提供反馈');
  await unchanged('无匹配');
  await clearSearch(scope, page, 'button', label);
  await search(scope, '<img src=x onerror="window.__workspaceInjected=true">', label + ':文本转义');
  assert.equal(await scope.locator('#moduleSearchResults img, #moduleSearchResults script, #moduleSearchResults iframe').count(), 0);
  assert.equal(await scope.evaluate(() => window.__workspaceInjected === true), false);
  await unchanged('恶意文本');
  await clearSearch(scope, page, 'escape', label);

  // 中文输入法组合期间保留既有结果，结束后才按完整查询更新。
  await search(scope, candidate.module, label + ':输入法组合前', candidate.module);
  const oldResults = await scope.locator('#moduleSearchResults button').evaluateAll(nodes => nodes.map(node => node.dataset.moduleId));
  await scope.locator('#moduleSearch').dispatchEvent('compositionstart');
  await scope.locator('#moduleSearch').evaluate(node => {
    node.value = '__workspace_composing_no_match__';
    node.dispatchEvent(new InputEvent('input', { bubbles: true, isComposing: true }));
  });
  assert.deepEqual(await scope.locator('#moduleSearchResults button').evaluateAll(nodes => nodes.map(node => node.dataset.moduleId)),
    oldResults, label + '输入法组合中不抢先改变匹配结果');
  await scope.locator('#moduleSearch').dispatchEvent('compositionend');
  await settle(scope);
  assert.equal(Number(await scope.locator('#moduleSearchResults').getAttribute('data-match-count')), 0);
  await clearSearch(scope, page, 'escape', label);

  await search(scope, candidate.module, label + ':结果区Esc', candidate.module);
  await scope.locator('#moduleSearchResults button').first().focus();
  await page.keyboard.press('Escape');
  assert.equal(await scope.locator('#moduleSearch').inputValue(), '');
  assert.equal(await scope.evaluate(() => document.activeElement?.id), 'moduleSearch', label + '结果区Esc返回搜索框');
  assert.equal(await scope.locator('#moduleSearchResults').evaluate(node => node.hidden), true);

  // '/'仅在普通页面焦点下触发；已有输入框、textarea和可编辑内容均保留输入。
  await scope.locator('h1').click();
  await page.keyboard.press('/');
  assert.equal(await scope.evaluate(() => document.activeElement?.id), 'moduleSearch', label + '/聚焦搜索');
  assert.equal(await scope.locator('#moduleSearch').inputValue(), '', label + '/快捷键不写入字符');
  await scope.locator('#provbtn').click();
  await scope.locator('#pfQ').fill('保持');
  await page.keyboard.press('/');
  assert.equal(await scope.evaluate(() => document.activeElement?.id), 'pfQ', label + '不抢溯源搜索框');
  assert.equal(await scope.locator('#pfQ').inputValue(), '保持/');
  assert.equal(await scope.locator('#moduleSearch').inputValue(), '');
  await scope.locator('#pfQ').fill('');
  for (const kind of ['textarea', 'editable']) {
    await scope.evaluate(type => {
      const node = document.createElement(type === 'textarea' ? 'textarea' : 'div');
      node.id = '__workspace_test_input';
      if (type === 'editable') node.contentEditable = 'true';
      node.setAttribute('aria-label', '工作台快捷键回归输入');
      node.style.cssText = 'position:fixed;left:4px;top:4px;width:150px;height:35px;z-index:9999';
      document.body.appendChild(node); node.focus();
    }, kind);
    try {
      await page.keyboard.press('/');
      assert.equal(await scope.evaluate(() => document.activeElement?.id), '__workspace_test_input', label + '不抢' + kind);
      const value = await scope.evaluate(() => { const node = document.getElementById('__workspace_test_input');
        return node.tagName === 'TEXTAREA' ? node.value : node.textContent; });
      assert.equal(value, '/');
    } finally { await scope.evaluate(() => document.getElementById('__workspace_test_input')?.remove()); }
  }

  // 优先搜索隐藏公司中的卡；按钮必须激活正确公司，并聚焦真实目标而不是另一个同源卡。
  const target = entries.find(entry => entry.hiddenCompany) || entries.at(-1);
  await search(scope, target.module, label + ':定位模块', target.module);
  const result = scope.locator(`#moduleSearchResults button[data-module-id="${target.module}"]`);
  assert.equal(await result.getAttribute('data-workspace-target'), target.id);
  await result.focus();
  await page.keyboard.press('Enter');
  await scope.waitForFunction(id => {
    const node = document.getElementById(id);
    return !!node && !node.closest('[data-copanel][hidden]') && document.activeElement === node &&
      node.classList.contains('workspace-highlight');
  }, target.id);
  await scope.waitForFunction(id => { const node = document.getElementById(id); const rect = node.getBoundingClientRect();
    return rect.top >= -1 && rect.top < innerHeight - 20; }, target.id);
  assert.equal(await scope.locator('#moduleSearchResults').evaluate(node => node.hidden), true,
    label + '选中后收起结果，避免遮盖已定位卡片');
  assert.equal(await scope.locator('#moduleSearch').inputValue(), target.module, label + '选中后保留查询');
  assert.equal(await scope.locator('#moduleSearch').getAttribute('aria-expanded'), 'false');
  assert.equal(await scope.locator('#workspaceOverview').getAttribute('data-search-active'), 'false');
  if (target.company) {
    const state = await scope.evaluate(id => { const node = document.getElementById(id);
      const group = node.closest('.mod'); return {
        selected: [...group.querySelectorAll('[data-cotab].on')].map(button => button.dataset.cotab),
        visible: [...group.querySelectorAll('[data-copanel]:not([hidden])')].map(panel => panel.dataset.copanel),
      }; }, target.id);
    assert.deepEqual(state.selected, [target.company], label + '搜索先激活目标公司');
    assert.deepEqual(state.visible, [target.company]);
    const chart = scope.locator(`[id="${target.id}"] .chart`).first();
    if (await chart.count()) {
      await settle(scope);
      const box = await chart.boundingBox();
      assert.ok(box && box.width > 100, label + '激活隐藏公司后图表仍有有效宽度');
    }
  }
  assert.equal(await scope.locator('[data-mid]').count(), entries.length, label + '定位后模块总数不变');
  await scope.locator('#moduleSearch').focus();
  assert.equal(await scope.locator('#moduleSearchResults').evaluate(node => node.hidden), false,
    label + '重新聚焦可继续查看原查询结果');
  assert.equal(await scope.locator('#moduleSearch').getAttribute('aria-expanded'), 'true');
  await search(scope, candidate.module, label + ':清除旧定位', candidate.module);
  await clearSearch(scope, page, 'button', label);
  assert.equal(await businessPayload(scope), beforePayload, label + '搜索不改业务载荷');
}

async function assertLayout(scope, page, label, output) {
  for (const width of widths) {
    await page.setViewportSize({ width, height: 1000 });
    await scope.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
    await settle(scope);
    const measured = await scope.evaluate(() => {
      const rect = node => { const box = node.getBoundingClientRect(); return {
        left: box.left, right: box.right, top: box.top, bottom: box.bottom, width: box.width, height: box.height,
      }; };
      const nav = document.getElementById('dnav');
      const ids = [...document.querySelectorAll('[id]')].map(node => node.id).filter(Boolean);
      return { client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth,
        nav: rect(nav), links: [...nav.querySelectorAll('a')].map(rect), main: rect(document.querySelector('.d-main')),
        input: rect(document.getElementById('moduleSearch')),
        departments: [...document.querySelectorAll('a[data-dashboard-page]')].map(rect),
        duplicates: [...new Set(ids.filter((id, i) => ids.indexOf(id) !== i))],
      };
    });
    assert.ok(measured.scroll <= measured.client + 1, `${label}整页不能横向溢出：${width}/${measured.scroll}`);
    assert.deepEqual(measured.duplicates, [], label + '不能复制目录产生重复ID');
    assert.ok(measured.input.width >= 100 && measured.input.left >= -1 && measured.input.right <= measured.client + 1,
      label + '搜索框在可用区域内：' + width);
    for (const box of measured.departments) assert.ok(box.width > 0 && box.height > 0 && box.left >= -1 &&
      box.right <= measured.client + 1, label + '顶部五部门入口均保留且不越界：' + width);
    if (width >= 1440) {
      assert.ok(measured.nav.width < 360 && measured.main.left >= measured.nav.right - 1,
        label + '桌面目录位于主内容左侧');
      assert.ok(measured.main.width >= 640, label + '侧栏不能压缩主内容至不可读');
      if (measured.links.length > 1) {
        assert.ok(measured.links[1].top >= measured.links[0].bottom - 2, label + '桌面目录纵向排列');
        assert.ok(Math.abs(measured.links[1].left - measured.links[0].left) <= 4);
      }
    } else if (measured.links.length > 1) {
      assert.ok(Math.abs(measured.links[1].top - measured.links[0].top) <= 4, label + '移动目录横向排列');
      assert.ok(measured.links[1].left >= measured.links[0].right - 2);
    }
    const topSize = await page.evaluate(() => ({ client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth }));
    assert.ok(topSize.scroll <= topSize.client + 1, label + '分享父壳不能横向溢出');
    await search(scope, 'P', label + ':窄屏结果');
    const results = await scope.locator('#moduleSearchResults').boundingBox();
    assert.ok(results && results.x >= -1 && results.x + results.width <= measured.client + 1,
      label + '结果面板不越出视口：' + width);
    await clearSearch(scope, page, 'escape', label);
    await search(scope, '超长无匹配查询'.repeat(30), label + ':长查询');
    const after = await scope.evaluate(() => ({ client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth }));
    assert.ok(after.scroll <= after.client + 1, label + '长查询不能撑开布局');
    await clearSearch(scope, page, 'button', label);
    output.push({ page: label, viewport: width, document: measured.scroll });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
}

async function serve() {
  const server = http.createServer((request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      const filename = path.resolve(directory, '.' + pathname);
      if (!filename.startsWith(directory + path.sep) || !fs.existsSync(filename) || !fs.statSync(filename).isFile()) {
        response.writeHead(404).end(); return;
      }
      const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.jpg': 'image/jpeg' };
      response.writeHead(200, { 'Content-Type': types[path.extname(filename)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
      fs.createReadStream(filename).pipe(response);
    } catch { response.writeHead(400).end(); }
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  return { server, origin: 'http://127.0.0.1:' + server.address().port };
}

(async () => {
  const { server, origin } = await serve();
  let browser;
  const contexts = [], errors = [], responsive = [];
  try {
    browser = await chromium.launch({ headless: true,
      ...(process.env.DNS_BROWSER_EXECUTABLE ? { executablePath: process.env.DNS_BROWSER_EXECUTABLE } : {}) });
    const makeContext = async offline => {
      const context = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 1440, height: 1000 }, offline });
      contexts.push(context);
      await context.route(/^https?:\/\//, route => route.request().url().startsWith(origin + '/')
        ? route.continue() : route.abort('blockedbyclient'));
      context.on('page', page => { page.setDefaultTimeout(15000);
        page.on('pageerror', error => errors.push(page.url() + ': ' + error.message)); });
      return context;
    };
    for (const mode of ['file', 'http']) {
      const context = await makeContext(false), page = await context.newPage();
      for (const view of views) {
        const url = mode === 'file' ? pathToFileURL(path.join(directory, view['文件'])).href
          : origin + '/' + encodeURIComponent(view['文件']);
        await page.goto(url, { waitUntil: 'load' });
        await assertSearch(page, page, view, mode + ':' + view.ID);
        await assertLayout(page, page, mode + ':' + view.ID, responsive);
      }
    }
    const context = await makeContext(true), page = await context.newPage();
    const shareUrl = pathToFileURL(path.join(directory, shareFilename)).href;
    for (const view of views) {
      await page.goto(shareUrl + '#page=' + view.ID, { waitUntil: 'load' });
      const frame = await shareFrame(page, view.ID);
      await assertSearch(frame, page, view, 'offline-share:' + view.ID);
      await assertLayout(frame, page, 'offline-share:' + view.ID, responsive);
      assert.equal(await page.locator('[data-dashboard-frame]').count(), 1, '检索后保留唯一分享iframe');
      assert.ok(decodeURIComponent(new URL(page.url()).pathname).endsWith('/' + shareFilename), '搜索跳转不脱离分享壳');
      assert.equal(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('page'), view.ID);
    }
    assert.deepEqual(errors, [], '工作台检索/布局与分享iframe零JS异常');
    console.log(JSON.stringify({ result: 'PASS', views: views.length, modes: ['file', 'http', 'offline-share'],
      search: ['名称', '模块ID', 'P号', '规划P号', '板块', '结果上限', '无匹配', '转义', '快捷键', '隐藏公司定位'],
      pageErrors: errors.length, responsive }));
  } finally {
    for (const context of contexts) await context.close();
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
