// 分页、整卡原文与可收缩目录的浏览器回归。只读取已构建产物，不构建、不采集。
// DNS_PLAYWRIGHT_MODULE / DNS_BROWSER_EXECUTABLE 复用本机运行时。
// DNS_INTERACTION_OUTPUT 指定截图目录；默认写入系统临时目录，不在仓库留下产物。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.DNS_PLAYWRIGHT_MODULE || 'playwright');

const directory = path.resolve(__dirname, '../看板');
const config = JSON.parse(fs.readFileSync(path.join(directory, '页面.json'), 'utf8').replace(/^\uFEFF/, ''));
const views = config['页面'];
const widths = [1440, 1100, 768, 390, 320];
const expectedCounts = { strategy: 101, marketing: 53, design: 16, product: 31, hr: 12 };
const shareName = '数据看板-单文件版.html';
const output = path.resolve(process.env.DNS_INTERACTION_OUTPUT || path.join(os.tmpdir(), 'dns-dashboard-interaction'));
const errors = [], checks = [], screenshots = [];
const script = name => fs.readFileSync(path.join(directory, '渲染器', name), 'utf8');
const sourceHash = require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(directory, 'data.js'))).digest('hex');

async function settle(scope) {
  await scope.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}
async function ready(scope, id) {
  await scope.waitForFunction(expected => typeof PAGE_INFO !== 'undefined' && PAGE_INFO.id === expected &&
    window.__provOK === true && window.DNSPager && document.getElementById('dns-dash')?.dataset.navigationReady === 'true', id);
  await settle(scope);
}
async function shareFrame(page, id) {
  const deadline = Date.now() + 20000;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const handle = await page.locator('[data-dashboard-frame]').elementHandle();
      const frame = handle && await handle.contentFrame();
      if (frame) {
        await frame.waitForFunction(expected => typeof PAGE_INFO !== 'undefined' && PAGE_INFO.id === expected &&
          window.__provOK === true && document.getElementById('dns-dash')?.dataset.navigationReady === 'true', id, { timeout: 600 });
        await ready(frame, id);
        return frame;
      }
    } catch (error) { lastError = error; }
    await page.waitForTimeout(40);
  }
  throw new Error('分享版未完成切换：' + id + '；' + (lastError?.message || '缺少iframe'));
}
async function screenshot(page, name) {
  const filename = path.join(output, name + '.png');
  await page.screenshot({ path: filename, fullPage: false, animations: 'disabled' });
  screenshots.push(filename);
}
async function top(scope) {
  await scope.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
  await settle(scope);
}

async function assertArticleContent(scope, label) {
  const result = await scope.evaluate(() => {
    const issues = [], omitted = typeof MEDIA_OMISSIONS === 'undefined' ? [] : MEDIA_OMISSIONS;
    const normalize = value => { try { const url = new URL(String(value || '')); return /^https?:$/.test(url.protocol) ? url.href : ''; } catch { return ''; } };
    const interactive = 'a[href],button,input,select,textarea,[contenteditable="true"],[role="button"]';
    let reviews = 0, news = 0, omissions = 0;
    document.querySelectorAll('[data-article-pid][data-article-index]').forEach(element => {
      const pid = element.dataset.articlePid, index = Number(element.dataset.articleIndex);
      const item = typeof REVIEWS === 'undefined' ? null : REVIEWS[pid]?.items?.[index];
      if (!item) { issues.push('图文索引不在真实载荷内：' + pid + '/' + index); return; }
      reviews++;
      const url = normalize(item.url);
      if (url && (element.tagName !== 'A' || element.href !== url || element.target !== '_blank')) issues.push('图文整卡必须指向原始http(s)来源：' + pid + '/' + index);
      if (url && !element.rel.split(/\s+/).includes('noopener')) issues.push('图文原文缺少noopener');
      if (element.querySelector(interactive)) issues.push('整卡内部不能嵌套第二个交互控件：' + pid + '/' + index);
      if (omitted.includes(item.img)) {
        omissions++;
        if (element.querySelector('img')) issues.push('待核对配图仍被展示：' + pid + '/' + index);
        if (!element.textContent.includes('图片待核对')) issues.push('待核对配图缺少诚实占位提示');
      }
    });
    document.querySelectorAll('[data-news]').forEach(container => {
      const source = (typeof NEWS === 'undefined' ? [] : NEWS[container.dataset.news] || []).filter(item => item && typeof item === 'object');
      const items = [...container.querySelectorAll('.news-item')];
      if (items.length !== source.length) issues.push('资讯DOM条数与原载荷不一致：' + container.dataset.news);
      items.forEach((item, index) => {
        news++;
        const entry = source[index], url = normalize(entry.url), link = item.querySelector('.fi.story-link');
        if (!link) { issues.push('资讯缺少整卡阅读结构'); return; }
        if (url && (link.tagName !== 'A' || link.href !== url || link.target !== '_blank')) issues.push('资讯整卡原文URL不一致');
        if (!url && link.hasAttribute('href')) issues.push('无有效来源的资讯不应生成假链接');
        if (link.querySelector(interactive)) issues.push('资讯整卡内部存在嵌套交互');
      });
    });
    if (document.querySelector('.review-preview,.review-source,.review-actions')) issues.push('旧图文双按钮仍在主页');
    document.querySelectorAll('[data-article-navigation="external"]').forEach(card => {
      if (card.querySelector('button[data-detail-module],button[data-detail-review],button[data-detail-index]')) issues.push('外链资料模块仍存在旧详情按钮');
    });
    return { issues, reviews, news, omissions };
  });
  assert.deepEqual(result.issues, [], label + '图文及新闻整卡使用真实来源，且没有旧双按钮或嵌套交互');
  assert.ok(result.reviews + result.news > 0, label + '确实检查了已有资讯或图文');
  return result;
}

async function assertCalendar(scope, label) {
  const calendars = await scope.evaluate(() => [...document.querySelectorAll('[data-calendar-news]')].map(section => {
    const pid = section.dataset.calendarNews, saved = typeof CAL === 'undefined' ? [] : CAL[pid]?.相关新闻 || [];
    const existing = [...saved, ...Object.values(typeof NEWS === 'undefined' ? {} : NEWS).flat()].map(item => {
      try { return { url: new URL(item.url).href, title: String(item.title_zh || item.title || '').trim() }; } catch { return null; }
    });
    return { pid, title: section.querySelector('h4')?.textContent || '', text: section.textContent,
      links: [...section.querySelectorAll('a[href]')].map(link => ({ url: link.href, target: link.target,
        safe: /^https?:$/.test(new URL(link.href).protocol), exists: existing.some(item => item && item.url === link.href &&
          item.title === (link.querySelector('.story-title')?.textContent || '').trim()) })),
      timeline: section.closest('.card')?.querySelector('[data-cal]')?.textContent || '' };
  }));
  for (const calendar of calendars) {
    assert.match(calendar.title, /相关新闻/, label + '议息日历保留相关资讯区');
    assert.ok(calendar.timeline.trim(), label + '资讯不替代真实会议日程');
    if (calendar.links.length) for (const link of calendar.links) {
      assert.ok(link.safe && link.exists && link.target === '_blank', label + '相关新闻只能引用已保存的http(s)来源：' + calendar.pid);
    } else assert.match(calendar.text, /暂无新消息|暂无可展示|暂无.*相关资讯/, label + '无资讯时明确为空，不能制造新闻');
  }
  return calendars.length;
}

async function assertNoInternalScroll(scope, label) {
  const bad = await scope.evaluate(() => [...document.querySelectorAll('.card,.revcards,[data-review],.feed,.revcard')]
    .filter(element => element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden')
    .filter(element => /^(auto|scroll)$/.test(getComputedStyle(element).overflowY) && element.scrollHeight > element.clientHeight + 3)
    .map(element => ({ cls: element.className, mid: element.closest('[data-mid]')?.dataset.mid,
      client: element.clientHeight, scroll: element.scrollHeight })));
  assert.deepEqual(bad, [], label + '资料卡与列表不保留内部纵向滚动区域');
}

async function assertNavigation(scope, page, width, label) {
  const toggle = scope.locator('#navigationToggle'), nav = scope.locator('#dnav');
  assert.equal(await toggle.getAttribute('aria-controls'), 'dnav', label + '目录按钮有明确控制关系');
  if (width >= 1280) {
    if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click();
    const expanded = await scope.locator('.workspace-stage').boundingBox();
    await toggle.focus(); await toggle.press('Space'); await settle(scope);
    assert.equal(await toggle.getAttribute('aria-expanded'), 'false', label + 'Space可收起桌面目录');
    const compact = await scope.locator('.workspace-stage').boundingBox();
    assert.ok(compact.width > expanded.width + 75, label + '目录收起必须释放真实内容宽度');
    assert.ok(compact.x < expanded.x - 75, label + '内容区向左扩展，不能留下空白侧栏');
    assert.match(await toggle.innerText(), /展开/, label + '收起后明确保留展开入口');
    for (const link of await nav.locator('a').all()) {
      assert.ok(await link.isVisible(), label + '编号快捷入口仍可用');
      assert.ok((await link.getAttribute('title') || '').trim(), label + '收起目录仍提供完整标题tooltip');
      assert.ok(await link.getAttribute('aria-label'), label + '编号链接仍有完整可访问名称');
    }
    await toggle.press('Enter'); await settle(scope);
    assert.equal(await toggle.getAttribute('aria-expanded'), 'true', label + 'Enter可重新展开目录');
    const restored = await scope.locator('.workspace-stage').boundingBox();
    assert.ok(Math.abs(restored.width - expanded.width) < 2, label + '展开后恢复内容布局');
  } else {
    if (await toggle.getAttribute('aria-expanded') === 'true') await toggle.click();
    assert.equal(await nav.isVisible(), false, label + '窄屏默认目录可收起');
    const bar = await scope.locator('.workspace-rail').boundingBox();
    assert.ok(bar.height <= 76, label + '收起目录不能占据大片页面');
    await toggle.focus(); await toggle.press('Enter'); await settle(scope);
    assert.equal(await toggle.getAttribute('aria-expanded'), 'true', label + '窄屏Enter可打开目录');
    assert.equal(await nav.isVisible(), true);
    const box = await nav.boundingBox();
    assert.ok(box.width > 100 && box.x >= -1 && box.x + box.width <= width + 1, label + '目录菜单不横向溢出');
    const destination = nav.locator('a').last(), target = (await destination.getAttribute('href')).slice(1);
    await destination.click(); await settle(scope);
    assert.equal(await toggle.getAttribute('aria-expanded'), 'false', label + '选中目录后自动收起');
    assert.equal(await scope.evaluate(() => document.activeElement.id), target, label + '键盘焦点交给目标板块');
    const position = await scope.locator('#' + target).boundingBox();
    assert.ok(position.y < 970 && position.y + position.height > 0, label + '目录点击确实定位到目标');
    await toggle.click(); await nav.locator('a').first().focus(); await page.keyboard.press('Escape');
    assert.equal(await toggle.getAttribute('aria-expanded'), 'false', label + 'Esc可收起窄屏目录');
    assert.equal(await toggle.evaluate(element => element === document.activeElement), true, label + 'Esc返回目录按钮');
  }
  await top(scope);
}

async function visiblePager(scope) {
  const index = await scope.locator('.content-pager').evaluateAll(elements => elements.findIndex(element =>
    element.getClientRects().length && Number(element.dataset.pageCount) > 1));
  assert.ok(index >= 0, '当前页面应有实际可翻页的资讯或图文');
  return scope.locator('.content-pager').nth(index);
}
async function pagerSnapshot(pager) {
  return pager.evaluate(element => ({ index: Number(element.dataset.pageIndex), count: Number(element.dataset.pageCount),
    visible: [...element.querySelector('.pager-items').children].filter(item => !item.hidden).map(item => item.textContent.trim()),
    total: element.querySelector('.pager-items').children.length }));
}
async function assertPagination(scope, label) {
  const pager = await visiblePager(scope), previous = pager.locator('.pager-previous'), next = pager.locator('.pager-next');
  await pager.evaluate(element => element.scrollIntoView({ block: 'center', behavior: 'instant' }));
  let snap = await pagerSnapshot(pager);
  for (let i = snap.index; i > 0; i--) await previous.click();
  const first = await pagerSnapshot(pager);
  assert.equal(first.index, 0); assert.equal(await previous.isDisabled(), true, label + '第一页禁用上一页');
  assert.ok(first.visible.length > 0 && first.visible.length < first.total, label + '分页只显示当前资料');
  await next.focus(); await next.press('Enter');
  const second = await pagerSnapshot(pager);
  assert.equal(second.index, 1, label + 'Enter可翻到下一页');
  assert.notDeepEqual(second.visible, first.visible, label + '翻页必须更换可见内容');
  assert.equal(second.total, first.total, label + '翻页不增删已保存的资料');
  await previous.focus(); await previous.press('Space');
  assert.equal((await pagerSnapshot(pager)).index, 0, label + 'Space可返回上一页');
  const totalPages = (await pagerSnapshot(pager)).count;
  for (let i = 1; i < totalPages; i++) await next.click();
  snap = await pagerSnapshot(pager);
  assert.equal(snap.index, totalPages - 1, label + '最后一页可抵达');
  assert.equal(await next.isDisabled(), true, label + '最后一页禁用下一页');
  assert.ok(snap.visible.length > 0 && snap.total === first.total, label + '末页保留真实资料与总条数');
  assert.equal(await pager.evaluate(element => !!element.querySelector('[hidden]:focus,[hidden] :focus,button:disabled:focus')), false,
    label + '焦点不能留在隐藏条目或刚禁用的翻页按钮');
  for (let i = totalPages - 1; i > 0; i--) await previous.click();
  assert.deepEqual((await pagerSnapshot(pager)).visible, first.visible, label + '反向翻页完整恢复首批条目');
  const controls = await pager.evaluate(element => ({ id: element.querySelector('.pager-items').id,
    previous: element.querySelector('.pager-previous').getAttribute('aria-controls'), next: element.querySelector('.pager-next').getAttribute('aria-controls'),
    live: element.querySelector('.pager-status').getAttribute('aria-live') }));
  assert.ok(controls.id && controls.id === controls.previous && controls.id === controls.next && controls.live === 'polite', label + '分页具备控制关系与页码播报');
  return pager;
}

async function assertGeometry(scope, page, view, width, label) {
  const measured = await scope.evaluate(() => {
    const ids = [...document.querySelectorAll('[id]')].map(element => element.id).filter(Boolean);
    return { client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth,
      count: document.querySelectorAll('[data-mid]').length,
      duplicates: [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))] };
  });
  assert.equal(measured.count, expectedCounts[view.ID], label + '模块数保持本轮调整前的真实数量');
  assert.deepEqual(measured.duplicates, [], label + '不能因分页/目录复制业务ID');
  assert.ok(measured.scroll <= measured.client + 1, label + '页面不能横向溢出');
  const parentSize = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
  assert.ok(parentSize.scroll <= parentSize.client + 1, label + '分享壳不能横向溢出');
  if (view.ID === 'strategy' && width >= 1280) {
    const logistics = await scope.evaluate(() => {
      const sea = document.querySelector('[data-mid="37_集装箱运价SCFI"]'), air = document.querySelector('[data-mid="38_空运运价需求口径"]');
      return { exists: !!sea && !!air, same: !!sea && !!air && !!sea.closest('.row') && sea.closest('.row') === air.closest('.row'),
        seaTop: sea?.getBoundingClientRect().top, airTop: air?.getBoundingClientRect().top };
    });
    assert.ok(logistics.exists && logistics.same && Math.abs(logistics.seaTop - logistics.airTop) <= 2,
      label + '海运成本与航空需求在桌面同一行并保留独立口径');
  }
  await assertNoInternalScroll(scope, label);
  return measured;
}

async function assertWheel(scope, page, label) {
  const pager = await visiblePager(scope);
  await pager.evaluate(element => { const rect = element.getBoundingClientRect(); scrollTo({ top: scrollY + rect.top - 240, behavior: 'instant' }); });
  await settle(scope);
  const box = await pager.boundingBox(), before = await scope.evaluate(() => scrollY);
  await page.mouse.move(box.x + box.width / 2, Math.min(box.y + 70, 750));
  await page.mouse.wheel(0, 540);
  await scope.waitForFunction(start => scrollY > start + 90, before);
  const internal = await pager.locator('.pager-items').evaluate(element => element.scrollTop);
  assert.equal(internal, 0, label + '鼠标位于资料卡时滚动整个页面，而不是卡内列表');
  await top(scope);
}

async function assertExternalClick(scope, page, selector, label) {
  const link = scope.locator(selector + ':visible').first();
  assert.ok(await link.count(), label + '存在可点击的整卡原文');
  const expected = await link.getAttribute('href'), before = page.url();
  const popupPromise = page.waitForEvent('popup');
  await link.click();
  const popup = await popupPromise;
  await popup.waitForLoadState('domcontentloaded');
  assert.equal(popup.url(), new URL(expected).href, label + '整卡直接在新页打开真实来源URL');
  assert.equal(page.url(), before, label + '原看板与分享路由保留');
  assert.equal(await scope.locator('dialog[open]').count(), 0, label + '整卡阅读不再打开旧图文模态详情');
  await popup.close();
}

async function fixtures(browser) {
  const context = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 900, height: 850 } });
  const page = await context.newPage(); page.on('pageerror', error => errors.push('fixture: ' + error.message));
  try {
    await page.setContent('<div id="dns-dash"><ul id="sample"></ul></div>');
    await page.addScriptTag({ content: script('04_pager.js') });
    await page.evaluate(() => {
      const list = document.getElementById('sample');
      for (let i = 0; i < 7; i++) { const item = document.createElement('li'), link = document.createElement('a'); link.href = '#item-' + i; link.textContent = '隔离分页样本' + i; item.appendChild(link); list.appendChild(item); }
      window.samplePager = DNSPager.mount(list, { label: '隔离样本', kind: 'news', pageSize: 3 });
    });
    const pager = page.locator('.content-pager');
    assert.deepEqual((await pagerSnapshot(pager)).visible, ['隔离分页样本0', '隔离分页样本1', '隔离分页样本2']);
    await page.evaluate(() => samplePager.goTo(999));
    assert.equal((await pagerSnapshot(pager)).index, 2, 'API越界页码安全限制到最后一页');
    assert.deepEqual((await pagerSnapshot(pager)).visible, ['隔离分页样本6'], '末页不补造空条目');
    await page.evaluate(() => samplePager.goTo(-99));
    assert.equal((await pagerSnapshot(pager)).index, 0, '负页码安全回到第一页');
    await page.evaluate(() => DNSPager.mount(document.getElementById('sample'), { label: '重新挂载' }));
    assert.equal(await page.locator('.content-pager').count(), 1, '重复挂载不能嵌套分页容器');
    await assertPagination(page, '隔离分页边界fixture');

    await page.setContent('<div id="dns-dash"><article class="card"><ul data-cal="P16"><li>保留会议日程</li></ul><p data-cal-desc="P16"></p><div class="foot"></div></article><article class="card"><ul data-cal="P20"><li>保留欧洲央行会议日程</li></ul><p data-cal-desc="P20"></p><div class="foot"></div></article></div>');
    await page.evaluate(() => {
      window.root = document.getElementById('dns-dash'); window.NEWS = {};
      window.CAL = { P16: { '相关新闻': [{ title: '隔离测试：货币政策公开信息', url: 'https://example.com/fixture-policy', date: '11-12', source: '隔离样本' }] }, P20: { '资讯采集': { '状态': '失败' } } };
      window.escH = value => { const span = document.createElement('span'); span.textContent = String(value == null ? '' : value); return span.innerHTML.replace(/"/g, '&quot;'); };
    });
    await page.addScriptTag({ content: script('04_pager.js') });
    await page.addScriptTag({ content: script('72_calendar.js') });
    assert.equal(await page.locator('[data-calendar-news="P16"] a').getAttribute('href'), 'https://example.com/fixture-policy', '议息资讯只展示注入的隔离来源');
    assert.equal(await page.locator('[data-calendar-news="P20"] a').count(), 0, '空资讯不能制造外链');
    assert.match(await page.locator('[data-calendar-news="P20"]').innerText(), /暂无新消息/);
    assert.match(await page.locator('[data-calendar-news="P20"]').innerText(), /暂未更新/);
    assert.match(await page.locator('[data-cal="P20"]').innerText(), /保留欧洲央行会议日程/);
    await page.setContent('<div id="dns-dash"><article data-news="sample"><ul class="feed"></ul></article><article data-news="empty"><ul class="feed"></ul></article><article class="card"><div data-review="90" class="revcards"></div></article></div>');
    await page.evaluate(() => {
      window.root = document.getElementById('dns-dash');
      window.NEWS = { sample: [{ title: '<script>window.__newsInjected=true</script>', url: 'javascript:alert(1)' },
        { title: '隔离样本：可追溯原文', url: 'https://example.com/news-fixture' }], empty: [] };
      window.MEDIA_OMISSIONS = ['data:image/png;base64,AA=='];
      window.REVIEWS = { P90: { items: [{ name: '隔离样本：待核对配图', url: 'https://example.com/review-fixture', img: 'data:image/png;base64,AA==' }] } };
    });
    await page.addScriptTag({ content: script('05_news.js') });
    await page.addScriptTag({ content: script('70_review.js') });
    assert.equal(await page.locator('[data-news="sample"] .news-item').first().locator('a[href]').count(), 0, '非法资讯URL不能成为可点击原文');
    assert.match(await page.locator('[data-news="sample"] .story-title').first().innerText(), /<script>/, '资讯标题按文字保留');
    assert.equal(await page.evaluate(() => window.__newsInjected), undefined, '资讯标题不能执行脚本');
    assert.equal(await page.locator('[data-news="sample"] a').getAttribute('href'), 'https://example.com/news-fixture');
    assert.equal(await page.locator('[data-news="empty"] a').count(), 0, '空资讯不制造原文入口');
    assert.match(await page.locator('[data-news="empty"]').innerText(), /无可展示|暂无/);
    assert.equal(await page.locator('[data-review="90"] img').count(), 0, 'MEDIA_OMISSIONS在独立图文渲染中仍生效');
    assert.match(await page.locator('[data-review="90"]').innerText(), /图片待核对/);
    assert.equal(await page.locator('a.revcard a,a.revcard button').count(), 0, '整张图文链接内部无嵌套操作');
    checks.push({ kind: 'fixtures', pager: 'boundary/remount/keyboard', calendar: 'saved-source/empty/failure/timeline',
      articles: 'invalid-url/text-escaping/empty/media-omissions' });
  } finally { await context.close(); }
}

async function serve() {
  const server = http.createServer((request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname), filename = path.resolve(directory, '.' + pathname);
      if (!filename.startsWith(directory + path.sep) || !fs.existsSync(filename) || !fs.statSync(filename).isFile()) return void response.writeHead(404).end();
      const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.jpg': 'image/jpeg', '.png': 'image/png' };
      response.writeHead(200, { 'Content-Type': types[path.extname(filename)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
      fs.createReadStream(filename).pipe(response);
    } catch { response.writeHead(400).end(); }
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  return { server, origin: 'http://127.0.0.1:' + server.address().port };
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const { server, origin } = await serve();
  let browser;
  const contexts = [];
  async function makeContext(options = {}) {
    const context = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 1440, height: 1000 }, ...options });
    contexts.push(context);
    await context.route(/^https?:\/\//, route => {
      if (route.request().url().startsWith(origin + '/')) return route.continue();
      // 外链点击使用相同URL的隔离响应验证，不访问源站；图片等远程资源一律阻断。
      if (route.request().isNavigationRequest()) return route.fulfill({ contentType: 'text/html', body: '<title>原文导航隔离验证</title><p>没有访问外部网站。</p>' });
      return route.abort('blockedbyclient');
    });
    context.on('page', page => { page.setDefaultTimeout(15000); page.on('pageerror', error => errors.push(page.url() + ': ' + error.message)); });
    return context;
  }
  try {
    browser = await chromium.launch({ headless: true, args: ['--explicitly-allowed-ports=' + new URL(origin).port],
      ...(process.env.DNS_BROWSER_EXECUTABLE ? { executablePath: process.env.DNS_BROWSER_EXECUTABLE } : {}) });
    for (const mode of ['file', 'offline-share']) {
      const context = await makeContext({ offline: mode === 'offline-share' }), page = await context.newPage();
      for (const view of views) {
        const url = mode === 'file' ? pathToFileURL(path.join(directory, view['文件'])).href : pathToFileURL(path.join(directory, shareName)).href + '#page=' + view.ID;
        await page.goto(url, { waitUntil: 'load' });
        const scope = mode === 'file' ? page : await shareFrame(page, view.ID);
        await ready(scope, view.ID);
        const articles = await assertArticleContent(scope, mode + ':' + view.ID);
        const calendars = await assertCalendar(scope, mode + ':' + view.ID);
        for (const width of widths) {
          await page.setViewportSize({ width, height: 1000 }); await settle(scope); await top(scope);
          const label = mode + ':' + view.ID + ':' + width;
          await assertNavigation(scope, page, width, label);
          await assertPagination(scope, label);
          await assertGeometry(scope, page, view, width, label);
          if (width === 1440 && ['strategy', 'design'].includes(view.ID)) await assertWheel(scope, page, label);
          if (mode === 'file' && view.ID === 'design' && width === 1440) {
            const pager = await visiblePager(scope); await pager.locator('.pager-next').click();
            await pager.evaluate(element => element.scrollIntoView({ block: 'center', behavior: 'instant' }));
            await screenshot(page, 'design-desktop-next-page');
          }
          await top(scope);
          if (['strategy', 'design'].includes(view.ID) && [1440, 390].includes(width)) await screenshot(page, mode + '-' + view.ID + '-' + width);
          checks.push({ mode, view: view.ID, width, articles, calendars });
          if (process.env.DNS_TEST_PROGRESS) console.log(JSON.stringify({ stage: 'interaction', mode, view: view.ID, width }));
        }
        await page.setViewportSize({ width: 1440, height: 1000 }); await settle(scope); await top(scope);
        if (view.ID === 'strategy') await assertExternalClick(scope, page, '.news-item a.story-link', mode + ':资讯整卡');
        if (view.ID === 'design') await assertExternalClick(scope, page, 'a.revcard.story-link', mode + ':图文整卡');
      }
    }

    // HTTP下的记忆状态与禁用存储分别验证，避免只覆盖file://的浏览器特例。
    const stateContext = await makeContext(), statePage = await stateContext.newPage();
    await statePage.goto(origin + '/index.html'); await ready(statePage, 'strategy');
    await statePage.locator('#navigationToggle').click();
    assert.equal(await statePage.locator('#navigationToggle').getAttribute('aria-expanded'), 'false');
    await statePage.locator('[data-dashboard-page="design"]').click(); await ready(statePage, 'design');
    assert.equal(await statePage.locator('#navigationToggle').getAttribute('aria-expanded'), 'false', '普通页跨部门记住桌面收起状态');
    await statePage.setViewportSize({ width: 390, height: 1000 }); await settle(statePage);
    await statePage.locator('#navigationToggle').click(); await statePage.reload(); await ready(statePage, 'design');
    assert.equal(await statePage.locator('#navigationToggle').getAttribute('aria-expanded'), 'true', '刷新恢复窄屏目录偏好');
    await statePage.locator('#navigationToggle').press('Escape');

    const blockedContext = await makeContext();
    await blockedContext.addInitScript(() => Object.defineProperty(window, 'localStorage', { configurable: true, get() { throw new DOMException('隔离测试：存储不可用', 'SecurityError'); } }));
    const blocked = await blockedContext.newPage();
    await blocked.goto(origin + '/index.html'); await ready(blocked, 'strategy');
    await assertNavigation(blocked, blocked, 1440, 'localStorage不可用');
    await blocked.goto(pathToFileURL(path.join(directory, shareName)).href + '#page=strategy');
    let blockedFrame = await shareFrame(blocked, 'strategy');
    await blockedFrame.locator('#navigationToggle').click();
    assert.equal(await blockedFrame.locator('#navigationToggle').getAttribute('aria-expanded'), 'false');
    await blockedFrame.locator('[data-dashboard-page="design"]').click(); blockedFrame = await shareFrame(blocked, 'design');
    assert.equal(await blockedFrame.locator('#navigationToggle').getAttribute('aria-expanded'), 'false', '分享iframe在存储禁用时通过父窗口保留偏好');

    // 真实触控手势从图文卡片开始，确认不拦截页面纵向滑动。
    const touchContext = await makeContext({ viewport: { width: 390, height: 900 }, hasTouch: true, isMobile: true });
    const touchPage = await touchContext.newPage(); await touchPage.goto(pathToFileURL(path.join(directory, 'design.html')).href); await ready(touchPage, 'design');
    const touchCard = touchPage.locator('a.revcard.story-link:visible').first();
    await touchCard.evaluate(element => { const box = element.getBoundingClientRect(); scrollTo({ top: scrollY + box.top - 260, behavior: 'instant' }); });
    await settle(touchPage);
    const touchBox = await touchCard.boundingBox(), start = await touchPage.evaluate(() => scrollY);
    const cdp = await touchContext.newCDPSession(touchPage), x = Math.round(touchBox.x + touchBox.width / 2), y = Math.round(Math.min(touchBox.y + touchBox.height - 25, 720));
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    for (let step = 1; step <= 6; step++) { await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: y - step * 40 }] }); await touchPage.waitForTimeout(20); }
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await touchPage.waitForFunction(before => scrollY > before + 60, start);
    await assertNoInternalScroll(touchPage, '手机真实触控'); await cdp.detach();
    checks.push({ kind: 'state-and-input', persistence: 'http/share/no-storage', input: 'real-mouse-wheel/real-touch-swipe' });

    await fixtures(browser);
    assert.deepEqual(errors, [], '所有交付、目录、分页和隔离场景均无JS异常');
    assert.equal(require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(directory, 'data.js'))).digest('hex'), sourceHash,
      '浏览器回归不写入或重生成业务数据');
    console.log(JSON.stringify({ result: 'PASS', views: views.length, modes: ['file', 'offline-share'], widths,
      responsiveCases: checks.filter(item => item.width).length, pageErrors: errors.length, screenshots, checks }, null, 2));
  } finally {
    for (const context of contexts) await context.close();
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
