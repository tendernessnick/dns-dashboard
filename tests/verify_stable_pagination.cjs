// 稳定分页回归：真实卡片、外层行及后续模块不因短页/空态/图片加载上下跳动。
// 仅读取产品源码与已构建产物；--fixtures-only可在最终构建前检查隔离场景。
// DNS_PLAYWRIGHT_MODULE / DNS_BROWSER_EXECUTABLE复用现有运行时；DNS_STABLE_OUTPUT指定仓库外截图及报告目录。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.DNS_PLAYWRIGHT_MODULE || 'playwright');

const directory = path.resolve(__dirname, '../看板');
const output = path.resolve(process.env.DNS_STABLE_OUTPUT || path.join(os.tmpdir(), 'dns-stable-pagination'));
const fixturesOnly = process.argv.includes('--fixtures-only');
const config = JSON.parse(fs.readFileSync(path.join(directory, '页面.json'), 'utf8').replace(/^\uFEFF/, ''));
const source = name => fs.readFileSync(path.join(directory, '渲染器', name), 'utf8');
const css = ['_style.css', '_workspace.css', '_pagination.css', '_navigation.css'].map(name => fs.readFileSync(path.join(directory, name), 'utf8')).join('\n');
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=', 'base64');
const dataImage = 'data:image/png;base64,' + png.toString('base64');
const tolerance = 1;
const errors = [], results = [], screenshots = [];

async function settle(scope) {
  await scope.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready;
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  });
}
async function responsiveReady(scope) {
  // 现有25_resize.js延迟重绘可见图表；先等待这些真实尺寸就绪，再归因分页的几何变化。
  await scope.waitForFunction(() => [...document.querySelectorAll('.chart')].every(element => {
    if (!element.clientWidth || !element.clientHeight) return true;
    const svg = element.querySelector('svg.terminal-plot');
    return !svg || (Math.abs(Number(svg.getAttribute('width')) - element.clientWidth) <= 1 &&
      Math.abs(Number(svg.getAttribute('height')) - element.clientHeight) <= 1);
  }));
  await settle(scope);
}
async function saveScreenshot(page, name, locator) {
  const filename = path.join(output, name + '.png');
  if (locator) {
    const viewport = page.viewportSize(), box = await locator.boundingBox();
    if (box && box.height + 180 > viewport.height) await page.setViewportSize({ width: viewport.width, height: Math.ceil(box.height + 180) });
    await locator.evaluate(element => scrollTo({ top: scrollY + element.getBoundingClientRect().top - 84, behavior: 'instant' }));
    await settle(page);
    await locator.screenshot({ path: filename, animations: 'disabled' });
  }
  else await page.screenshot({ path: filename, fullPage: false, animations: 'disabled' });
  screenshots.push(filename);
}
async function ready(scope, id) {
  await scope.waitForFunction(expected => typeof PAGE_INFO !== 'undefined' && PAGE_INFO.id === expected &&
    window.__provOK === true && window.DNSPager && document.getElementById('dns-dash')?.dataset.navigationReady === 'true', id);
  await settle(scope);
}
async function shareFrame(page, id) {
  const deadline = Date.now() + 20000;
  let failure;
  while (Date.now() < deadline) {
    try {
      const handle = await page.locator('[data-dashboard-frame]').elementHandle();
      const frame = handle && await handle.contentFrame();
      if (frame) {
        await frame.waitForFunction(expected => typeof PAGE_INFO !== 'undefined' && PAGE_INFO.id === expected &&
          document.getElementById('dns-dash')?.dataset.navigationReady === 'true', id, { timeout: 500 });
        await ready(frame, id); return frame;
      }
    } catch (error) { failure = error; }
    await page.waitForTimeout(40);
  }
  throw new Error('分享版切换未完成：' + id + '；' + (failure?.message || '缺少iframe'));
}

async function geometry(pager) {
  return pager.evaluate(element => {
    const shown = node => !!node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
    const box = node => {
      if (!node) return null;
      const rect = node.getBoundingClientRect();
      return { top: rect.top + scrollY, height: rect.height, bottom: rect.bottom + scrollY, width: rect.width };
    };
    const card = element.closest('.card[data-mid],.card'), row = card?.closest('.row'), section = card?.closest('.mod');
    const rows = [...document.querySelectorAll('.row')].filter(shown), rowIndex = rows.indexOf(row);
    const nextRow = rowIndex >= 0 ? rows[rowIndex + 1] : null;
    const cards = [...document.querySelectorAll('.card[data-mid]')].filter(shown), index = cards.indexOf(card);
    const downstream = cards.slice(index + 1).find(candidate => !row || candidate.closest('.row') !== row);
    const sections = [...document.querySelectorAll('.mod')].filter(shown), sectionIndex = sections.indexOf(section);
    const nextSection = sectionIndex >= 0 ? sections[sectionIndex + 1] : null;
    return { pager: box(element), card: box(card), row: box(row), nextRow: box(nextRow), downstream: box(downstream), nextSection: box(nextSection),
      downstreamId: downstream?.dataset.mid || '', scrollY, documentHeight: document.documentElement.scrollHeight,
      page: Number(element.dataset.pageIndex), pages: Number(element.dataset.pageCount), count: Number(element.dataset.itemCount),
      visible: [...element.querySelector('.pager-items').children].filter(item => !item.hidden && !item.matches('[data-pager-empty],.feed-empty,.top-empty,.rev-empty')).map(item => item.textContent.trim()),
      status: element.querySelector('.pager-status')?.textContent || '' };
  });
}
function assertStable(before, after, label, options = {}) {
  for (const key of ['pager', 'card', 'row', 'nextRow', 'downstream', 'nextSection']) {
    assert.equal(Boolean(after[key]), Boolean(before[key]), label + '保留实际布局对象：' + key);
    if (!before[key]) continue;
    for (const field of ['top', 'height']) assert.ok(Math.abs(after[key][field] - before[key][field]) <= tolerance,
      `${label} ${key}.${field}不能跳动：${before[key][field]} → ${after[key][field]}`);
  }
  assert.equal(after.downstreamId, before.downstreamId, label + '跟踪同一后续业务卡');
  if (options.scroll) assert.ok(Math.abs(after.scrollY - before.scrollY) <= tolerance,
    label + '翻页不应自动滚动主页面：' + before.scrollY + ' → ' + after.scrollY);
}

async function assertNoOverflow(scope, label) {
  const measured = await scope.evaluate(() => {
    const root = document.getElementById('dns-dash');
    const bad = [...root.querySelectorAll('.content-pager,.pager-items,.pager-item,.card')]
      .filter(element => element.getClientRects().length && /^(auto|scroll)$/.test(getComputedStyle(element).overflowY) &&
        element.scrollHeight > element.clientHeight + 2)
      .map(element => ({ cls: element.className, mid: element.closest('[data-mid]')?.dataset.mid, client: element.clientHeight, scroll: element.scrollHeight }));
    return { client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth, bad };
  });
  assert.deepEqual(measured.bad, [], label + '不能用内部纵向滚动掩盖高度问题');
  assert.ok(measured.scroll <= measured.client + 1, label + '页面不能横向溢出：' + measured.scroll + '/' + measured.client);
}
async function assertFocus(pager, label) {
  assert.equal(await pager.evaluate(element => {
    const active = document.activeElement;
    return !!active && element.contains(active) && (active.matches(':disabled') || !!active.closest('[hidden]') || !active.getClientRects().length);
  }), false, label + '焦点不能留在禁用按钮或隐藏页');
}

async function exercisePager(scope, pager, label, options = {}) {
  const previous = pager.locator('.pager-previous'), next = pager.locator('.pager-next');
  let initial = await geometry(pager);
  assert.ok(Number.isFinite(initial.count) && initial.count >= 0, label + '分页提供真实条数');
  assert.ok(initial.pager.height > 50 && initial.card && initial.row, label + '检查真实卡与行，不能只检查分页按钮');
  const nodes = await pager.locator('.pager-items').evaluate(element => [...element.children]
    .filter(item => !item.matches('[data-pager-empty],.feed-empty,.top-empty,.rev-empty')).length);
  assert.equal(nodes, initial.count, label + 'DOM中仅保留真实条目，不靠补假条目撑高');
  for (const arrow of [previous, next]) {
    assert.equal(await arrow.isVisible(), true, label + '0条/单页也保留统一控制区');
    const box = await arrow.boundingBox();
    assert.ok(box.width >= 43.5 && box.height >= 43.5, label + '保留至少44px可操作区域');
  }
  if (initial.pages < 2) {
    assert.equal(await previous.isDisabled(), true); assert.equal(await next.isDisabled(), true);
    if (initial.count === 0) {
      assert.doesNotMatch(initial.status, /共\s*1\s*条|1\s*\/\s*1/, label + '不能将空态作为一条资讯');
      assert.equal(await pager.locator('.pager-empty-state').isVisible(), true);
      assert.match(await pager.locator('.pager-empty-state').innerText(), /暂无新消息/, label + '中心保留诚实空态');
    }
    return initial;
  }
  for (let step = initial.page; step > 0; step--) await previous.click();
  await next.evaluate(element => element.scrollIntoView({ behavior: 'instant', block: 'center' }));
  await settle(scope);
  initial = await geometry(pager);
  assert.equal(initial.page, 0); assert.equal(await previous.isDisabled(), true);
  const snapshots = [initial];
  for (let page = 1; page < initial.pages; page++) {
    if (page === 1) { await next.focus(); await next.press('Enter'); }
    else await next.click();
    await settle(scope);
    const after = await geometry(pager);
    assert.equal(after.page, page, label + '到达指定页');
    assert.equal(after.count, initial.count, label + '翻页不改变真实条数');
    assert.ok(after.visible.length > 0, label + '末页不能只有占位条目');
    assertStable(initial, after, label + ':第' + (page + 1) + '页', { scroll: true });
    await assertFocus(pager, label); snapshots.push(after);
  }
  assert.equal(await next.isDisabled(), true, label + '末页禁用下一页');
  for (let page = initial.pages - 2; page >= 0; page--) {
    if (page === initial.pages - 2) { await previous.focus(); await previous.press('Space'); }
    else await previous.click();
    await settle(scope);
    const after = await geometry(pager);
    assert.equal(after.page, page); assertStable(initial, after, label + ':回退' + page, { scroll: true });
    await assertFocus(pager, label);
  }
  assert.deepEqual((await geometry(pager)).visible, initial.visible, label + '回到首批原始条目');
  if (options.record !== false) results.push({ type: 'paging', label, count: initial.count, pages: initial.pages,
    maxCardDelta: Math.max(...snapshots.map(item => Math.abs(item.card.height - initial.card.height))),
    maxDownstreamDelta: Math.max(...snapshots.map(item => Math.abs((item.downstream?.top || 0) - (initial.downstream?.top || 0)))) });
  return initial;
}

function fixtureMarkup(kind) {
  const contents = kind === 'review' ? '<div class="revcards" data-review="900" id="fixture-items"></div>'
    : kind === 'toplist' ? '<ul class="feed" data-toplist="P900" id="fixture-items"></ul>'
      : kind === 'calendar' ? '<ul class="tl-list" data-cal="P16"><li>隔离会议日程</li></ul><p class="desc" data-cal-desc="P16">隔离决议说明</p>'
        : '<ul class="feed" id="fixture-items"></ul>';
  return '<style>' + css + '\n#dns-dash .fixture-stage{width:calc(100% - 36px);max-width:1180px;margin:24px auto;min-width:0}'
    + '#dns-dash .fixture-stage>.mod{margin-bottom:30px}#dns-dash .fixture-spacer{height:700px}</style>'
    + '<div id="dns-dash"><main class="fixture-stage"><section class="mod" id="fixture-section"><div class="sec-head"><h2>分页隔离场景</h2></div>'
    + '<div class="row" id="fixture-row"><article class="card c12" data-mid="fixture-owner"' + (kind === 'news' ? ' data-news="fixture"' : '') + '>'
    + '<div class="card-top"><span class="t">真实业务卡外壳</span></div>' + contents + '<div class="foot">保留来源脚注</div></article></div>'
    + '<div class="row" id="fixture-next-row"><article class="card c12" data-mid="fixture-downstream"><h3>同板块下一张业务卡</h3><p>此处位置不能因上一张卡换页而变化。</p></article></div></section>'
    + '<section class="mod" id="fixture-next-section"><div class="sec-head"><h2>下一个业务板块</h2></div><div class="row"><article class="card c12" data-mid="fixture-last"><p>用于检查下游板块的位置。</p></article></div></section>'
    + '<div class="fixture-spacer"></div></main></div>';
}
async function setFixtureData(page, kind, count, images) {
  await page.evaluate(({ kind, count, images, dataImage }) => {
    const now = new Date(), iso = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
    const items = Array.from({ length: count }, (_, index) => ({
      title: index % 2 ? 'Long original policy headline ' + 'original text '.repeat(18) + index : 'Short original ' + index,
      title_zh: index % 2 ? '长标题用于核对各页保留的空间，确保内容长短不会引发页面位置变化。'.repeat(9) + index : '短消息' + index,
      name: index % 2 ? '图文产品长标题与设计功能说明'.repeat(14) + index : '短产品名' + index,
      url: 'https://article.fixture.test/detail-' + index, date: iso.slice(5), iso, source: index % 2 ? '公开资料来源' : '',
      desc: index % 3 ? '已保存的资料摘要，长短内容混合用于核对分页布局。'.repeat(16) : '',
      summary: index % 3 ? '已有摘要资料。'.repeat(25) : '',
      img: images?.[index] ?? (index % 2 ? '' : dataImage), tag: index % 2 ? '产品体验' : '',
      chips: index % 2 ? ['额定功率65W', '重量120g', '双接口', '公开参数', '原文数据', '快照'] : [],
      rank: index + 1, asin: 'B00000000' + index, price: index % 2 ? 9.99 : 159.99
    }));
    window.NEWS = { fixture: items }; window.REVIEWS = { P900: { items } }; window.TOPS = { P900: { items, total: count } };
    window.CAL = { P16: { '时间线': [{ '日期': '隔离日期', '文本': '隔离会议日程' }], '说明': '隔离决议说明', '相关新闻': items } };
    window.root = document.getElementById('dns-dash'); window.MEDIA_OMISSIONS = [];
    window.escH = value => { const span = document.createElement('span'); span.textContent = String(value == null ? '' : value); return span.innerHTML.replace(/"/g, '&quot;'); };
  }, { kind, count, images, dataImage });
  if (kind === 'news') await page.addScriptTag({ content: source('05_news.js') });
  if (kind === 'review') await page.addScriptTag({ content: source('70_review.js') });
  if (kind === 'toplist') { await page.addScriptTag({ content: source('60_toplist.js') }); await page.addScriptTag({ content: source('62_feedfade.js') }); }
  if (kind === 'calendar') await page.addScriptTag({ content: source('72_calendar.js') });
  const container = page.locator('[data-mid="fixture-owner"] .pager-items');
  assert.equal(await container.count(), 1, kind + '空态也使用统一分页容器');
  // 重复挂载实际容器，覆盖旧WeakMap实例的configure/refresh，而非仅创建一次的理想场景。
  await container.evaluate((element, kind) => DNSPager.mount(element, { kind: kind === 'calendar' ? 'news' : kind,
    ...(kind === 'calendar' ? { variant: 'calendar', pageSize: 2 } : {}), label: '隔离' + kind }), kind);
  await settle(page);
  assert.equal(await page.locator('[data-mid="fixture-owner"] .content-pager').count(), 1, kind + '重新挂载不能嵌套分页');
  return page.locator('[data-mid="fixture-owner"] .content-pager');
}

async function fixtureMatrix(makeContext) {
  for (const width of [1440, 1600, 390, 320]) for (const kind of ['news', 'review', 'toplist', 'calendar']) {
    const context = await makeContext({ viewport: { width, height: 1000 } }), page = await context.newPage();
    try {
      await page.setContent(fixtureMarkup(kind));
      await page.addScriptTag({ content: source('04_pager.js') });
      let pager = await setFixtureData(page, kind, 7);
      const full = await exercisePager(page, pager, 'fixture:' + kind + ':' + width);
      const capacity = full.visible.length;
      assert.ok(capacity >= 1 && capacity <= 3, kind + '当前页数量遵守控件宽度');
      for (const count of [1, 0, capacity, capacity + 1, 0, 1]) {
        pager = await setFixtureData(page, kind, count);
        const state = await geometry(pager);
        assert.equal(state.count, count, kind + ':' + width + '只统计真实条目（包括0条）');
        assertStable(full, state, 'fixture:' + kind + ':' + width + ':重挂载' + count + '条');
        if (count === 0) {
          assert.equal(await pager.locator('.pager-empty-state').isVisible(), true);
          assert.match(await pager.locator('.pager-empty-state').innerText(), /暂无新消息/);
          assert.doesNotMatch(state.status, /共\s*1\s*条/);
          if (kind === 'calendar') {
            await page.evaluate(() => { CAL.P16['资讯采集'] = { '状态': '失败' }; });
            await page.addScriptTag({ content: source('72_calendar.js') }); await settle(page);
            assertStable(state, await geometry(pager), 'calendar:' + width + ':失败说明不挤动空态');
            assert.match(await page.locator('.calendar-news-status').innerText(), /暂未更新/);
          }
        }
        await exercisePager(page, pager, 'fixture:' + kind + ':' + width + ':' + count + '条', { record: false });
      }
      pager = await setFixtureData(page, kind, 7);
      const standardSize = await geometry(pager);
      await page.evaluate(() => document.getElementById('dns-dash').classList.add('large-reading'));
      await settle(page);
      assert.ok((await geometry(pager)).pager.height > standardSize.pager.height + 10, kind + '字号放大实际扩展保留空间');
      await exercisePager(page, pager, 'fixture:' + kind + ':' + width + ':字号放大');
      const alternateWidth = width >= 1280 ? 390 : 1600;
      await page.setViewportSize({ width: alternateWidth, height: 1000 }); await settle(page);
      const resized = await exercisePager(page, pager, 'fixture:' + kind + ':' + alternateWidth + ':ResizeObserver重排');
      if (kind !== 'calendar') assert.notEqual(resized.visible.length, capacity, kind + '跨桌面手机宽度时ResizeObserver确实改变每页容量');
      await assertNoOverflow(page, 'fixture:' + kind + ':' + width);
      results.push({ type: 'fixture-counts', kind, width, counts: [0, 1, capacity, capacity + 1], enlarged: true, resized: alternateWidth });
      if (width === 390 && kind === 'calendar') {
        await page.setViewportSize({ width, height: 1000 });
        await page.evaluate(() => document.getElementById('dns-dash').classList.remove('large-reading'));
        await settle(page);
        pager = await setFixtureData(page, kind, 0);
        await saveScreenshot(page, 'fixture-calendar-empty-390', page.locator('[data-mid="fixture-owner"]'));
      }
    } finally { await context.close(); }
  }
}

async function lateImages(makeContext) {
  for (const kind of ['review', 'toplist']) {
    const context = await makeContext({ viewport: { width: 390, height: 1000 } }), page = await context.newPage();
    const pending = [];
    await context.route('https://stable-media.fixture.test/**', route => new Promise(resolve => pending.push(async () => {
      try { await route.fulfill({ status: 200, contentType: route.request().url().includes('failed') ? 'text/html' : 'image/png',
        body: route.request().url().includes('failed') ? '<title>隔离404兜底</title>' : png }); } finally { resolve(); }
    })));
    try {
      await page.setContent(fixtureMarkup(kind)); await page.addScriptTag({ content: source('04_pager.js') });
      const pager = await setFixtureData(page, kind, 2, ['https://stable-media.fixture.test/late-success.png', 'https://stable-media.fixture.test/late-failed.jpg']);
      await pager.evaluate(element => { element.scrollIntoView({ behavior: 'instant', block: 'center' }); element.querySelectorAll('img').forEach(img => { img.loading = 'eager'; }); });
      await page.waitForFunction(() => [...document.images].length > 0);
      await settle(page); const before = await geometry(pager);
      const deadline = Date.now() + 4000;
      while (pending.length < 2 && Date.now() < deadline) await page.waitForTimeout(20);
      assert.equal(pending.length, 2, kind + '确实延迟了成功和失败两张图片');
      await Promise.all(pending.splice(0).map(release => release()));
      await page.waitForFunction(() => [...document.images].every(img => img.complete)); await settle(page);
      assertStable(before, await geometry(pager), '图片后加载/HTTP200失败:' + kind);
      if (kind === 'review') {
        assert.equal(await page.locator('.rmedia[data-media-state="loaded"]').count(), 1);
        assert.equal(await page.locator('.rmedia[data-media-state="load-error"]').count(), 1);
      } else {
        assert.equal(await pager.locator('img').count(), 1, '榜单失败图片被移除，保留成功图片');
        assert.equal(await pager.locator('img').evaluate(image => image.complete && image.naturalWidth > 0), true);
      }
      await exercisePager(page, pager, '图片生命周期结束后翻页:' + kind);
      await assertNoOverflow(page, '图片后加载:' + kind);
      results.push({ type: 'late-images', kind, delayed: 2, http200Html: true });
    } finally { await Promise.all(pending.splice(0).map(release => release().catch(() => {}))); await context.close(); }
  }
}

async function hiddenPanelFixture(makeContext) {
  const context = await makeContext({ viewport: { width: 1440, height: 1000 } }), page = await context.newPage();
  try {
    await page.setContent('<style>' + css + '#dns-dash{padding:20px}.fixture-spacer{height:1000px}</style><div id="dns-dash"><section class="mod">'
      + '<div class="co-tabs"><button data-cotab="甲" aria-pressed="true">甲公司</button><button data-cotab="乙" aria-pressed="false">乙公司</button></div>'
      + ['甲', '乙'].map((name, index) => '<div class="co-panel" data-copanel="' + name + '"' + (index ? ' hidden' : '') + '><div class="row"><article class="card c12" data-mid="panel-' + index + '" data-news="panel-' + index + '"><div class="card-top"><span class="t">同一规格资讯模块</span></div><ul class="feed"></ul><div class="foot">来源</div></article></div></div>').join('')
      + '<div class="row"><article class="card c12" data-mid="panel-after">共同后续模块</article></div></section><div class="fixture-spacer"></div></div>');
    await page.evaluate(() => {
      window.root = document.getElementById('dns-dash'); window.drawChart = () => {};
      window.NEWS = { 'panel-0': Array.from({ length: 7 }, (_, i) => ({ title: i % 2 ? '长消息'.repeat(45) : '短消息', url: 'https://article.fixture.test/a-' + i })),
        'panel-1': [{ title: '仅有一条消息', url: 'https://article.fixture.test/b' }] };
    });
    await page.addScriptTag({ content: source('04_pager.js') }); await page.addScriptTag({ content: source('05_news.js') });
    await page.addScriptTag({ content: source('40_copanel.js') }); await settle(page);
    const first = page.locator('[data-mid="panel-0"] .content-pager'), firstGeometry = await exercisePager(page, first, '隐藏公司fixture:甲');
    await page.locator('[data-cotab="乙"]').click(); await settle(page);
    const second = page.locator('[data-mid="panel-1"] .content-pager'), secondGeometry = await geometry(second);
    assert.ok(Math.abs(firstGeometry.card.height - secondGeometry.card.height) <= tolerance, '隐藏面板出现后采用正确宽度和同等槽位');
    assert.ok(Math.abs(firstGeometry.downstream.top - secondGeometry.downstream.top) <= tolerance, '不同公司条数不使共同后续模块跳动');
    assert.equal(secondGeometry.count, 1);
    await page.locator('[data-cotab="甲"]').click(); await settle(page);
    await exercisePager(page, first, '隐藏公司fixture:再次显示');
    await assertNoOverflow(page, '隐藏公司fixture'); results.push({ type: 'hidden-company-fixture', counts: [7, 1] });
  } finally { await context.close(); }
}

async function production(makeContext) {
  for (const mode of ['file', 'offline-share']) {
    const context = await makeContext({ offline: mode === 'offline-share' }), page = await context.newPage();
    try {
      for (const view of config['页面']) {
        const url = pathToFileURL(path.join(directory, mode === 'file' ? view['文件'] : '数据看板-单文件版.html')).href + (mode === 'file' ? '' : '#page=' + view.ID);
        await page.goto(url, { waitUntil: 'load' });
        const scope = mode === 'file' ? page : await shareFrame(page, view.ID); await ready(scope, view.ID);
        const widths = ['strategy', 'design'].includes(view.ID) ? [1440, 1600, 390, 320] : [1440, 390];
        for (const width of widths) {
          await page.setViewportSize({ width, height: 1000 }); await responsiveReady(scope);
          const selected = await scope.locator('.content-pager').evaluateAll(elements => {
            const chosen = [], seen = new Set();
            elements.forEach((element, index) => {
              if (!element.getClientRects().length) return;
              const calendar = element.closest('[data-calendar-news]')?.dataset.calendarNews;
              const kind = calendar ? 'calendar-' + calendar : element.dataset.pagerKind;
              if (!seen.has(kind)) { seen.add(kind); chosen.push({ index, kind }); }
            }); return chosen;
          });
          assert.ok(selected.length > 0, mode + ':' + view.ID + '确实存在可检查资料模块');
          for (const item of selected) await exercisePager(scope, scope.locator('.content-pager').nth(item.index),
            mode + ':' + view.ID + ':' + width + ':' + item.kind);
          await assertNoOverflow(scope, mode + ':' + view.ID + ':' + width);
          if (mode === 'file' && view.ID === 'strategy' && [1440, 390].includes(width)) {
            for (const pid of ['P16', 'P20']) {
              const calendar = scope.locator('[data-calendar-news="' + pid + '"]').locator('..');
              await saveScreenshot(page, 'strategy-calendar-' + pid + '-' + width + '-stable', calendar);
              const active = scope.locator('[data-calendar-news="' + pid + '"] .content-pager');
              if (await active.count() && !(await active.locator('.pager-next').isDisabled())) {
                await active.locator('.pager-next').click(); await settle(scope);
                await saveScreenshot(page, 'strategy-calendar-' + pid + '-' + width + '-next', calendar);
              }
            }
          }
          results.push({ type: 'production-layout', mode, view: view.ID, width, kinds: selected.map(item => item.kind) });
          if (process.env.DNS_TEST_PROGRESS) console.log(JSON.stringify({ stage: 'stable-layout', mode, view: view.ID, width }));
        }
        // 真正隐藏的公司面板在显示后才获得可用宽度，抽样战略/市场的另一家公司。
        if (['strategy', 'marketing'].includes(view.ID)) {
          await page.setViewportSize({ width: 1440, height: 1000 }); await settle(scope);
          const button = scope.locator('[data-cotab][aria-pressed="false"]').first();
          if (await button.count()) {
            const company = await button.getAttribute('data-cotab'); await button.click(); await settle(scope);
            const panel = scope.locator('[data-copanel]').filter({ has: scope.locator('.content-pager') });
            const choices = await panel.evaluateAll((elements, company) => elements.filter(element => element.dataset.copanel === company && !element.hidden).map(element => element.dataset.copanel), company);
            assert.ok(choices.includes(company));
            const pager = scope.locator('[data-copanel="' + company + '"] .content-pager').first();
            await exercisePager(scope, pager, mode + ':' + view.ID + ':公司切换:' + company);
          }
        }
      }
    } finally { await context.close(); }
  }
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  let browser;
  async function makeContext(options = {}) {
    const context = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 1440, height: 1000 }, timezoneId: 'America/Los_Angeles', ...options });
    await context.route(/^https?:\/\//, route => route.abort('blockedbyclient'));
    context.on('page', page => { page.setDefaultTimeout(15000); page.on('pageerror', error => errors.push(page.url() + ': ' + error.message)); });
    return context;
  }
  try {
    browser = await chromium.launch({ headless: true, ...(process.env.DNS_BROWSER_EXECUTABLE ? { executablePath: process.env.DNS_BROWSER_EXECUTABLE } : {}) });
    await fixtureMatrix(makeContext); await lateImages(makeContext); await hiddenPanelFixture(makeContext);
    if (!fixturesOnly) await production(makeContext);
    assert.deepEqual(errors, [], '分页、空态、字体与图片生命周期零JS异常');
    const report = { result: 'PASS', fixturesOnly, tolerancePx: tolerance,
      productionCases: results.filter(item => item.type === 'production-layout').length,
      fixtureCountCases: results.filter(item => item.type === 'fixture-counts').length,
      pageErrors: errors.length, screenshots, checks: results };
    fs.writeFileSync(path.join(output, fixturesOnly ? 'stable-fixtures-result.json' : 'stable-pagination-result.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } catch (error) {
    fs.writeFileSync(path.join(output, 'stable-pagination-failure.json'), JSON.stringify({ result: 'FAIL', message: error.message, stack: error.stack, errors, checks: results }, null, 2));
    throw error;
  } finally { if (browser) await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
