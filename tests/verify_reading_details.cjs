// v25阅读与详情浏览器回归；仅读取已构建的五页与分享版，不构建/采集/写入业务数据。
// DNS_PLAYWRIGHT_MODULE 指定已有Playwright；DNS_BROWSER_EXECUTABLE 可指定Chrome。
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.DNS_PLAYWRIGHT_MODULE || 'playwright');
const directory = path.resolve(__dirname, '../看板');
const config = JSON.parse(fs.readFileSync(path.join(directory, '页面.json'), 'utf8').replace(/^\uFEFF/, ''));
const views = config['页面'];
const shareFilename = '数据看板-单文件版.html';
const focused = process.env.DNS_DETAILS_FOCUSED === '1';
const sourceHash = crypto.createHash('sha256').update(fs.readFileSync(path.join(directory, 'data.js'))).digest('hex');
function progress(stage, view) {
  if (process.env.DNS_TEST_PROGRESS) console.log(JSON.stringify({ stage, view }));
}

async function tick(scope) {
  await scope.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function ready(scope, view) {
  await scope.waitForFunction(id => typeof PAGE_INFO !== 'undefined' && PAGE_INFO.id === id && window.__provOK === true &&
    document.querySelector('#moduleDetail') && document.querySelector('#moduleSearch')?.dataset.workspaceSearchReady === 'true', view.ID);
  await tick(scope);
}

async function frameFor(page, view) {
  const end = Date.now() + 15000;
  let lastError;
  while (Date.now() < end) {
    try {
      const handle = await page.locator('[data-dashboard-frame]').elementHandle();
      const frame = handle && await handle.contentFrame();
      if (frame) {
        await frame.waitForFunction(id => typeof PAGE_INFO !== 'undefined' && PAGE_INFO.id === id &&
          !!document.getElementById('moduleDetail') && window.__provOK === true, view.ID, { timeout: 600 });
        await ready(frame, view);
        return frame;
      }
    } catch (error) { lastError = error; }
    await page.waitForTimeout(40);
  }
  throw new Error('分享壳详情页加载失败：' + view.ID + '; ' + (lastError?.message || '无iframe'));
}

async function payload(scope) {
  return scope.evaluate(() => JSON.stringify({ data: DDATA, bind: BIND, win: WIN, meta: META, news: NEWS, tops: TOPS,
    reviews: typeof REVIEWS === 'undefined' ? {} : REVIEWS, cal: typeof CAL === 'undefined' ? {} : CAL, prov: PROV }));
}

async function ids(scope) {
  return scope.evaluate(() => [...document.querySelectorAll('[data-mid]')].map(node => node.dataset.mid).sort());
}

async function assertDialog(scope, label) {
  const dialog = scope.locator('#moduleDetail');
  assert.equal(await dialog.count(), 1, label + '只有一个详情dialog');
  assert.equal(await dialog.evaluate(node => node.tagName), 'DIALOG');
  assert.equal(await dialog.evaluate(node => node.open), true, label + '详情已打开');
  assert.ok(await dialog.evaluate(node => node.matches(':modal')), label + '使用原生模态前景');
  assert.ok((await dialog.locator('#detailTitle').innerText()).trim(), label + '详情标题可见');
  assert.equal(await dialog.locator('[data-mid]').count(), 0, label + '详情不复制业务模块身份');
  assert.equal(await dialog.locator('#moduleSearch,#dnav,#appendix').count(), 0);
  const text = await dialog.innerText();
  assert.ok(!/\b(?:undefined|NaN|null)\b/.test(text), label + '详情不能暴露null/undefined/NaN');
  const badLinks = await dialog.locator('a[href]').evaluateAll(nodes => nodes.filter(node => {
    try { return !/^https?:$/.test(new URL(node.href).protocol); } catch { return true; }
  }).map(node => node.getAttribute('href')));
  assert.deepEqual(badLinks, [], label + '详情仅允许http(s)原文来源链接');
  const duplicateIds = await scope.evaluate(() => {
    const values = [...document.querySelectorAll('[id]')].map(node => node.id).filter(Boolean);
    return [...new Set(values.filter((id, index) => values.indexOf(id) !== index))];
  });
  assert.deepEqual(duplicateIds, [], label + '详情没有重复DOM ID');
  return dialog;
}

async function open(scope, locator, label) {
  await locator.scrollIntoViewIfNeeded();
  await locator.click();
  await scope.waitForFunction(() => document.getElementById('moduleDetail').open);
  await tick(scope);
  return assertDialog(scope, label);
}

async function close(scope, page, trigger, method, label) {
  if (method === 'escape') await page.keyboard.press('Escape');
  else await scope.locator('#moduleDetail ' + (method === 'bottom' ? '.detail-close-bottom' : '.detail-close')).click();
  await scope.waitForFunction(() => !document.getElementById('moduleDetail').open);
  assert.ok(await trigger.evaluate(node => document.activeElement === node), label + '关闭回到原触发按钮');
}

async function validateTables(scope, label) {
  const tables = scope.locator('#moduleDetail table.detail-table[data-detail-table]');
  assert.ok(await tables.count(), label + '数值详情包含真实数据表');
  let cells = 0;
  for (const table of await tables.all()) {
    const pid = await table.getAttribute('data-detail-table');
    const expected = await scope.evaluate(id => ({ cols: DDATA[id]?.cols, rows: DDATA[id]?.rows,
      unit: BIND[id]?.[0] || '' }), pid);
    assert.ok(expected.cols && expected.rows?.length, label + '表绑定真实P号：' + pid);
    const headers = await table.locator('thead th').allTextContents();
    for (const column of expected.cols) assert.ok(headers.some(header => header.includes(column)), label + '保留数值列：' + column);
    const shownRows = await table.locator('tbody tr').evaluateAll(nodes => nodes.map(node =>
      [...node.querySelectorAll('td')].map(cell => cell.textContent.trim())));
    assert.ok(shownRows.length > 0 && shownRows.length <= expected.rows.length);
    for (const row of shownRows) {
      assert.ok(/^\d{4}-\d{2}-\d{2}$/.test(row[0]), label + '表格保留完整观测日期');
      const candidates = expected.rows.filter(item => item[0] === row[0]);
      assert.ok(candidates.length, label + '日期在原始载荷存在：' + row[0]);
      const matches = candidates.some(candidate => expected.cols.every((column, index) => {
        const value = candidate[index + 1], actual = row[index + 1];
        if (value === null || value === undefined || value === '') return actual === '—';
        if (typeof value !== 'number') return actual === String(value);
        const parsed = Number(String(actual).replace(/,/g, '').replace(/%$/, '').trim());
        return Number.isFinite(parsed) && Math.abs(parsed - value) <= Math.max(1e-9, Math.abs(value) * 1e-10);
      }));
      assert.ok(matches, label + '数据表保留原值，不四舍五入损失或伪造：' + pid + '/' + JSON.stringify(row));
      cells += expected.cols.length;
    }
    if (expected.unit) assert.ok((await scope.locator('#moduleDetail').innerText()).includes(expected.unit), label + '明确数值单位：' + expected.unit);
  }
  return cells;
}

async function modalKeyboard(scope, page, trigger, label) {
  const dialog = scope.locator('#moduleDetail');
  const focusables = dialog.locator('button:not([disabled]),a[href],input,select,textarea,[tabindex="0"]');
  const visible = [];
  for (const item of await focusables.all()) if (await item.isVisible()) visible.push(item);
  assert.ok(visible.length >= 2, label + '详情有可用关闭与动作');
  await visible.at(-1).focus();
  await page.keyboard.press('Tab');
  assert.ok(await dialog.evaluate(node => node.contains(document.activeElement)), label + '末尾Tab不离开模态层');
  await visible[0].focus();
  await page.keyboard.press('Shift+Tab');
  assert.ok(await dialog.evaluate(node => node.contains(document.activeElement)), label + '首项反向Tab不离开模态层');
  await dialog.locator('.detail-close').focus();
  await page.keyboard.press('/');
  assert.ok(await dialog.evaluate(node => node.contains(document.activeElement)), label + '详情前景不会被全局/快捷键抢焦点');
  await close(scope, page, trigger, 'escape', label);
}

async function latestShare(scope, label) {
  for (const chart of await scope.locator('[data-share]').all()) {
    const pid = await chart.getAttribute('data-share');
    const expected = await scope.evaluate(id => {
      const data = DDATA[id];
      const last = data.rows.filter(row => row?.[0]).reduce((a, b) => String(a[0]) > String(b[0]) ? a : b);
      const entries = data.cols.map((column, index) => ({ label: String(column).replace(/%$/, ''), index,
        value: Number.isFinite(last[index + 1]) && last[index + 1] >= 0 && last[index + 1] <= 100 ? last[index + 1] : null }));
      entries.sort((a, b) => a.value === null ? (b.value === null ? a.index - b.index : 1)
        : b.value === null ? -1 : b.value - a.value || a.index - b.index);
      return { date: last[0], rows: entries.map(item => ({ label: item.label, value: item.value === null ? '—' : item.value + '%' })) };
    }, pid);
    assert.ok((await chart.innerText()).includes(expected.date), label + '份额横条明确最新观测日期');
    const shown = await chart.locator('.share-rank-row').evaluateAll(rows => rows.map(row => ({
      label: row.querySelector('.share-brand').textContent.trim(), value: row.querySelector('.share-value').textContent.trim(),
    })));
    assert.deepEqual(shown, expected.rows, label + '最新期横向排行使用真实份额排序，不改历史载荷');
    assert.equal(await chart.locator('.dpill,.chg').count(), 0, label + '份额排序不伪装成增减');
  }
}

async function mediaPolicy(scope, label) {
  const problems = await scope.evaluate(() => {
    const omitted = typeof MEDIA_OMISSIONS === 'undefined' ? [] : MEDIA_OMISSIONS;
    return [...document.querySelectorAll('[data-article-pid][data-article-index]')].flatMap(article => {
      const pid = article.dataset.articlePid;
      const item = REVIEWS[pid]?.items[Number(article.dataset.articleIndex)];
      if (!item?.img) return [];
      if (omitted.includes(item.img)) return article.querySelector('img') || !article.textContent.includes('图片待核对')
        ? ['重复配图未明确拦截:' + pid + '/' + item.name] : [];
      return article.querySelector('img') ? [] : ['安全图文配图不应无故消失:' + pid + '/' + item.name];
    });
  });
  assert.deepEqual(problems, [], label + '重复头像不冒充产品图，安全配图仍可展示');
}

async function announcementSemantics(scope, page, label) {
  const trigger = scope.locator('[data-mid^="81_"] button[data-detail-module]').first();
  if (!(await trigger.count())) return;
  const data = await scope.evaluate(() => DDATA.P81);
  const onlyIndex = data?.cols?.length && data.cols.every(column => /序号|排名|名次|编号|^id$|索引/i.test(column));
  const dialog = await open(scope, trigger, label + ':公告编号边界');
  if (onlyIndex) assert.equal(await dialog.locator('.detail-chart,.chart').count(), 0,
    label + '公告序号不是业务指标，不能绘制虚假趋势');
  if (data?.rows?.length) await validateTables(scope, label + ':公告原表');
  assert.ok(await dialog.locator('a.detail-source-link').count(), label + '公告资料保留公开来源或原文入口');
  await close(scope, page, trigger, 'close', label + ':公告编号边界');
}

async function assertDetails(scope, page, view, label) {
  await ready(scope, view);
  const beforePayload = await payload(scope), beforeModules = await ids(scope);
  await latestShare(scope, label);
  await mediaPolicy(scope, label);
  await announcementSemantics(scope, page, label);
  assert.equal(beforeModules.length, await scope.evaluate(() => PAGE_INFO.moduleCount));
  const missingActions = await scope.locator('[data-mid]').evaluateAll(cards => cards
    .filter(card => card.querySelectorAll('button[data-detail-module]').length !== (card.dataset.articleNavigation === 'external' ? 0 : 1)).map(card => card.dataset.mid));
  assert.deepEqual(missingActions, [], label + '数值和说明保留详情，资讯图文整卡直达原文且不再重复预览入口');
  const reading = scope.locator('#readingSize');
  assert.equal(await reading.count(), 1, label + '提供主动放大阅读');
  assert.equal(await reading.getAttribute('aria-pressed'), 'false');
  const titleSelector = '.card:not([hidden]) .card-top .t';
  const titleBefore = await scope.locator(titleSelector).first().evaluate(node => parseFloat(getComputedStyle(node).fontSize));
  await reading.click();
  assert.equal(await reading.getAttribute('aria-pressed'), 'true');
  const titleAfter = await scope.locator(titleSelector).first().evaluate(node => parseFloat(getComputedStyle(node).fontSize));
  assert.ok(titleAfter > titleBefore, label + '主动阅读模式确实放大文字');
  await reading.click();
  assert.equal(await reading.getAttribute('aria-pressed'), 'false');
  const numerical = await scope.locator('[data-mid]').evaluateAll(cards => cards.map(card => ({
    id: card.dataset.mid, pid: (card.dataset.k || '').split(/\s+/)[0],
    hidden: !!card.closest('[data-copanel][hidden]'), numericUI: !!card.querySelector('.val,.chart,[data-multi]'),
  })).find(card => !card.hidden && card.numericUI && card.pid && DDATA['P' + card.pid]?.rows?.length &&
    DDATA['P' + card.pid].cols?.some(column => !/排名/.test(column))));
  if (['strategy', 'product'].includes(view.ID)) assert.ok(numerical, label + '配置中的真实数值模块应能展开');
  if (numerical) {
    const numericButton = scope.locator(`[data-mid="${numerical.id}"] button[data-detail-module="${numerical.id}"]`);
    await open(scope, numericButton, label + ':数值');
    await validateTables(scope, label + ':数值');
    await modalKeyboard(scope, page, numericButton, label + ':数值键盘');
  } else {
    const description = await scope.locator('[data-mid]').evaluateAll(cards => cards
      .filter(card => card.dataset.moduleStatus !== 'planned' && card.querySelector('button[data-detail-module]') && !card.closest('[data-copanel][hidden]'))
      .map(card => ({ id: card.dataset.mid, pids: (card.dataset.sourcePids || '').split(/\s+/).filter(Boolean) }))
      .find(card => !card.pids.some(pid => DDATA[pid]?.rows?.length)));
    assert.ok(description, label + '无数值页保留真实说明或资讯入口');
    const trigger = scope.locator(`[data-mid="${description.id}"] button[data-detail-module="${description.id}"]`);
    const dialog = await open(scope, trigger, label + ':公开说明');
    assert.equal(await dialog.locator('table[data-detail-table],.vnum,.dpill').count(), 0,
      label + '没有数值记录的公开说明不能制造数据');
    await modalKeyboard(scope, page, trigger, label + ':公开说明键盘');
  }

  const sampleButton = scope.locator('button[data-detail-module^="72_"]').first();
  if (await sampleButton.count()) {
    const dialog = await open(scope, sampleButton, label + ':样本价格');
    assert.match(await dialog.innerText(), /样本|分箱/);
    assert.match(await dialog.innerText(), /未按销量加权|非销量|席位|商品数/);
    await validateTables(scope, label + ':样本价格');
    await close(scope, page, sampleButton, 'bottom', label + ':样本价格');
  }
  const topButton = scope.locator('button[data-detail-module^="66_"],button[data-detail-module^="68_"]').first();
  if (await topButton.count()) {
    const dialog = await open(scope, topButton, label + ':榜单');
    const text = await dialog.innerText();
    assert.match(text, /榜单|Best Sellers|Amazon/);
    const expected = await scope.evaluate(() => ({ P66: TOPS.P66, P68: TOPS.P68 }));
    const pid = (await topButton.getAttribute('data-detail-module')).startsWith('66_') ? 'P66' : 'P68';
    assert.ok(text.includes(expected[pid].date), label + '榜单详情显示快照日期');
    assert.ok(text.includes(String(expected[pid].total)), label + '榜单明确全快照样本数，不把可见5项当全榜');
    assert.ok(text.includes('$') || text.includes('美元') || text.includes('USD'), label + '榜单价格保留币种');
    const decodedTitles = await scope.evaluate(id => TOPS[id].items.map(item => {
      const text = document.createElement('textarea'); text.innerHTML = item.title; return text.value;
    }), pid);
    for (const title of decodedTitles) assert.ok(text.includes(title), label + '榜单详情显示正确还原的已转义原标题');
    await close(scope, page, topButton, 'close', label + ':榜单');
  }

  assert.equal(await scope.locator('button[data-detail-review],.review-preview,.review-source').count(), 0,
    label + '图文使用整卡原文链接，不保留双操作');
  const articleProblems = await scope.locator('a[data-article-pid][data-article-index]').evaluateAll(links => links.flatMap(link => {
    const item = REVIEWS[link.dataset.articlePid]?.items[Number(link.dataset.articleIndex)];
    return !item || link.href !== new URL(item.url).href || !link.textContent.includes(item.name)
      || link.target !== '_blank' || !link.rel.includes('noopener') || link.querySelector('a,button,input')
      ? [link.dataset.articlePid + ':' + link.dataset.articleIndex] : [];
  }));
  assert.deepEqual(articleProblems, [], label + '图文原题与原文逐项对应，整卡外链不嵌套交互');
  const plannedButton = scope.locator('.planned-card button[data-detail-module]').first();
  assert.ok(await plannedButton.count(), label + '本部门保留规划模块');
  const planCard = plannedButton.locator('xpath=ancestor::*[@data-mid][1]');
  const plannedNumber = await planCard.getAttribute('data-planned-id');
  const planTitle = await planCard.locator('.card-top .t').innerText();
  const plannedDialog = await open(scope, plannedButton, label + ':规划');
  assert.ok((await plannedDialog.innerText()).includes(plannedNumber));
  assert.ok((await plannedDialog.innerText()).includes(planTitle));
  assert.equal(await plannedDialog.locator('.detail-planned .chip.c-planned').count(), 1);
  assert.equal(await plannedDialog.locator('table[data-detail-table],.vnum,.dpill,.chart,.chip.c-ok').count(), 0,
    label + '规划详情只有说明，没有假数据和已接入状态');
  assert.match(await plannedDialog.innerText(), /尚未|未接入|规划/);
  await close(scope, page, plannedButton, 'escape', label + ':规划');

  // 只在浏览器内临时注入坏URL，关闭后恢复；不写业务文件、不访问恶意来源。
  const sourceTarget = await scope.locator('[data-mid][data-source-pids]').evaluateAll(cards => cards
    .filter(card => !card.closest('[data-copanel][hidden]') && card.querySelector('button[data-detail-module]'))
    .map(card => ({ id: card.dataset.mid, pids: card.dataset.sourcePids.split(/\s+/) }))
    .find(card => card.pids.some(pid => PROV.some(source => 'P' + source.id === pid))));
  if (sourceTarget) {
    await scope.evaluate(target => {
      const source = PROV.find(source => target.pids.includes('P' + source.id));
      window.__readingSavedSource = { source, url: source.url };
      source.url = 'javascript:window.__readingBadLinkExecuted=true';
    }, sourceTarget);
    const button = scope.locator(`[data-mid="${sourceTarget.id}"] button[data-detail-module="${sourceTarget.id}"]`);
    try {
      await open(scope, button, label + ':来源恶链');
      const bad = await scope.locator('#moduleDetail a[href]').evaluateAll(nodes => nodes.filter(node =>
        !/^https?:$/.test(new URL(node.href).protocol)).map(node => node.getAttribute('href')));
      assert.deepEqual(bad, [], label + '拒绝javascript来源URL');
      assert.equal(await scope.evaluate(() => window.__readingBadLinkExecuted === true), false);
      await close(scope, page, button, 'close', label + ':来源恶链');
    } finally {
      await scope.evaluate(() => { const old = window.__readingSavedSource; if (old) old.source.url = old.url;
        delete window.__readingSavedSource; delete window.__readingBadLinkExecuted; });
    }
  }
  assert.deepEqual(await ids(scope), beforeModules, label + '打开详情不能增加或复制模块');
  assert.equal(await payload(scope), beforePayload, label + '详情不改业务载荷');
}

async function numericEdgeCases(scope, page, label) {
  const pid = await scope.evaluate(() => {
    const available = [...document.querySelectorAll('button[data-detail-pid]')]
      .map(node => node.dataset.detailPid).filter(id => DDATA[id]?.rows?.length);
    return available.includes('P21') ? 'P21' : available[0];
  });
  assert.ok(pid, label + '战略精选指标具有P号详情入口');
  const button = scope.locator(`button[data-detail-pid="${pid}"]`).first();
  await scope.evaluate(id => {
    const source = DDATA[id];
    window.__readingSavedRows = { id, rows: source.rows, cols: source.cols };
    source.cols = ['零值测试', '缺失测试', '空字符串测试', '原始精度测试'];
    source.rows = [['2026-01-01', 0, null, '', 6.71912345]];
  }, pid);
  try {
    await open(scope, button, label + ':零与缺失');
    assert.equal(await scope.locator('#moduleDetail table[data-detail-table]').count(), 1,
      label + '精选单P入口不扩展成整个聚合模块');
    const values = await scope.locator(`#moduleDetail table[data-detail-table="${pid}"] tbody tr`).first()
      .locator('td').allTextContents();
    assert.deepEqual(values.map(value => value.trim()), ['2026-01-01', '0', '—', '—', '6.71912345'],
      label + '零保留、null/空为—、原始精度保留');
    await close(scope, page, button, 'close', label + ':零与缺失');
  } finally {
    await scope.evaluate(() => { const old = window.__readingSavedRows;
      if (old) { DDATA[old.id].rows = old.rows; DDATA[old.id].cols = old.cols; }
      delete window.__readingSavedRows; });
  }
  // 长序列必须有继续阅读入口，不能把首批50行当全部历史。
  const historical = await scope.evaluate(() => [...document.querySelectorAll('[data-mid][data-k]')]
    .filter(node => !node.closest('[data-copanel][hidden]'))
    .map(node => ({ id: node.dataset.mid, pid: 'P' + node.dataset.k.split(/\s+/)[0] }))
    .find(item => DDATA[item.pid]?.rows?.length > 50));
  if (historical) {
    await scope.locator('.pctl button[data-m="3"]').click();
    const trigger = scope.locator(`[data-mid="${historical.id}"] button[data-detail-module="${historical.id}"]`);
    await open(scope, trigger, label + ':历史分页');
    const fullChart = scope.locator(`#moduleDetail .detail-chart[data-chart="${historical.pid}"]`).first();
    if (await fullChart.count()) {
      await tick(scope);
      const column = Number(await fullChart.getAttribute('data-col'));
      const expectedPoints = await scope.evaluate(({ id, column }) => DDATA[id].rows
        .filter(row => row[column] !== null && row[column] !== undefined).length, { id: historical.pid, column });
      const points = await fullChart.locator('polyline.line-a').getAttribute('points');
      assert.equal(points.trim().split(/\s+/).length, expectedPoints,
        label + '详情趋势显示完整历史，不被主页三个月窗口截断');
      assert.equal(await scope.evaluate(() => PSEL.months), 3, label + '详情绘制不能改全局周期选择');
    }
    const table = scope.locator(`#moduleDetail table[data-detail-table="${historical.pid}"]`);
    assert.equal(await table.locator('tbody tr').count(), 50);
    const total = await scope.evaluate(pid => DDATA[pid].rows.length, historical.pid);
    assert.ok((await table.locator('caption').innerText()).includes(String(total)), label + '历史表说明总行数');
    await scope.locator('#moduleDetail .detail-load-more').first().click();
    assert.ok(await table.locator('tbody tr').count() > 50, label + '继续加载真实历史');
    await validateTables(scope, label + ':加载历史');
    await close(scope, page, trigger, 'bottom', label + ':历史分页');
    await scope.locator('.pctl button').first().click();
  }
}

async function readingLayout(scope, page, label, results) {
  // 720 CSS像素对应1440px桌面以200%放大时的有效阅读宽度；不把DPR变化误作缩放。
  const sizes = [{ width: 320, zoom: 1 }, { width: 390, zoom: 1 }, { width: 768, zoom: 1 },
    { width: 1440, zoom: 1 }, { width: 720, zoom: 2 }];
  for (const size of sizes) {
    await page.setViewportSize({ width: size.width, height: 1000 });
    await scope.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
    await tick(scope);
    const measurements = await scope.evaluate(() => ({ client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
      coverage: [...document.querySelectorAll('details.coverage-summary')].map(node => node.open),
      buttons: [...document.querySelectorAll('button[data-detail-module],button[data-detail-review],button[data-detail-pid]')]
        .filter(node => node.getClientRects().length && !node.closest('[data-copanel][hidden]'))
        .map(node => { const box = node.getBoundingClientRect(); return { label: node.textContent.trim(), width: box.width, height: box.height }; }),
    }));
    assert.ok(measurements.scroll <= measurements.client + 1, label + '阅读页无横向溢出：' + JSON.stringify(size));
    assert.ok(measurements.coverage.length && measurements.coverage.every(open => !open), label + '覆盖统计默认折叠');
    for (const button of measurements.buttons) assert.ok(button.width >= 43.5 && button.height >= 43.5,
      label + '明确详情动作至少44px：' + JSON.stringify(button));
    const candidate = scope.locator('button[data-detail-module^="72_"]').first();
    let trigger = await candidate.count() ? candidate : null;
    if (!trigger) for (const button of await scope.locator('button[data-detail-module]').all()) {
      if (await button.isVisible()) { trigger = button; break; }
    }
    assert.ok(trigger, label + '至少有可用详情动作');
    await open(scope, trigger, label + ':响应详情');
    const geometry = await scope.locator('#moduleDetail').evaluate(node => {
      const box = node.getBoundingClientRect();
      return { left: box.left, right: box.right, top: box.top, bottom: box.bottom,
        width: box.width, client: document.documentElement.clientWidth,
        scroll: document.documentElement.scrollWidth, viewportHeight: innerHeight,
        body: node.querySelector('.detail-body')?.getBoundingClientRect().height || 0,
      };
    });
    assert.ok(geometry.left >= -1 && geometry.right <= geometry.client + 1 && geometry.top >= -1 &&
      geometry.bottom <= geometry.viewportHeight + 1, label + '详情始终位于可用视口：' + JSON.stringify(size));
    assert.ok(geometry.scroll <= geometry.client + 1, label + '详情表格不能撑宽整页');
    assert.ok(geometry.body > 50, label + '详情内容区域可阅读');
    const focusButton = scope.locator('#moduleDetail .detail-close');
    const box = await focusButton.boundingBox();
    assert.ok(box && box.width >= 43.5 && box.height >= 43.5, label + '关闭按钮至少44px');
    // 若表格宽于容器，必须由详情内部显式横滚容器承接。
    const badTables = await scope.locator('#moduleDetail table').evaluateAll(tables => tables.filter(table => {
      let node = table.parentElement;
      while (node && node.id !== 'moduleDetail') {
        const css = getComputedStyle(node);
        if (/(auto|scroll)/.test(css.overflowX)) return false;
        node = node.parentElement;
      }
      return table.scrollWidth > table.closest('dialog').clientWidth + 1;
    }).map(table => table.getAttribute('data-detail-table')));
    assert.deepEqual(badTables, [], label + '宽表格在详情内部横滚');
    await close(scope, page, trigger, 'escape', label + ':响应详情');
    results.push({ page: label, viewport: size.width, zoomEquivalent: size.zoom, document: measurements.scroll });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
}

async function serve() {
  const server = http.createServer((request, response) => {
    try {
      const filename = path.resolve(directory, '.' + decodeURIComponent(new URL(request.url, 'http://localhost').pathname));
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
  const contexts = [], errors = [], layouts = [];
  try {
    browser = await chromium.launch({ headless: true, args: ['--explicitly-allowed-ports=' + new URL(origin).port],
      ...(process.env.DNS_BROWSER_EXECUTABLE ? { executablePath: process.env.DNS_BROWSER_EXECUTABLE } : {}) });
    async function makeContext(offline) {
      const context = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 1440, height: 1000 }, offline });
      contexts.push(context);
      await context.route(/^https?:\/\//, route => route.request().url().startsWith(origin + '/')
        ? route.continue() : route.abort('blockedbyclient'));
      context.on('page', page => { page.setDefaultTimeout(15000);
        page.on('pageerror', error => errors.push(page.url() + ': ' + error.message)); });
      return context;
    }
    for (const mode of ['file', 'http']) {
      const context = await makeContext(false), page = await context.newPage();
      for (const view of views) {
        const url = mode === 'file' ? pathToFileURL(path.join(directory, view['文件'])).href
          : origin + '/' + encodeURIComponent(view['文件']);
        await page.goto(url, { waitUntil: 'load' });
        const label = mode + ':' + view.ID;
        if (focused) {
          await ready(page, view); await mediaPolicy(page, label); await announcementSemantics(page, page, label);
          progress('media-announcement-pass', label); continue;
        }
        await assertDetails(page, page, view, label);
        progress('details-pass', label);
        if (view.ID === config['默认页面']) await numericEdgeCases(page, page, label);
        await readingLayout(page, page, label, layouts);
        progress('layout-pass', label);
      }
    }
    const context = await makeContext(true), page = await context.newPage();
    const sharedUrl = pathToFileURL(path.join(directory, shareFilename)).href;
    await page.goto(sharedUrl + '#page=' + config['默认页面'], { waitUntil: 'load' });
    let previous;
    for (const view of views) {
      if (previous) {
        // 父路由在模态层打开时也能释放旧iframe，不遗留遮罩、焦点或锁滚状态。
        await page.evaluate(id => { location.hash = 'page=' + id; }, view.ID);
      } else if (view.ID !== config['默认页面']) await page.evaluate(id => { location.hash = 'page=' + id; }, view.ID);
      const frame = await frameFor(page, view);
      assert.equal(await frame.locator('#moduleDetail').evaluate(node => node.open), false, '切部门后详情默认关闭');
      assert.equal(await frame.locator('dialog[open]').count(), 0);
      if (focused) {
        await mediaPolicy(frame, 'offline-share:' + view.ID);
        await announcementSemantics(frame, page, 'offline-share:' + view.ID);
        progress('media-announcement-pass', 'offline-share:' + view.ID); previous = view; continue;
      }
      await assertDetails(frame, page, view, 'offline-share:' + view.ID);
      progress('details-pass', 'offline-share:' + view.ID);
      await readingLayout(frame, page, 'offline-share:' + view.ID, layouts);
      progress('layout-pass', 'offline-share:' + view.ID);
      const trigger = frame.locator('button[data-detail-module]').first();
      await open(frame, trigger, 'offline-share:切页前详情');
      previous = view;
    }
    await page.reload({ waitUntil: 'load' });
    const refreshed = await frameFor(page, views.at(-1));
    assert.equal(await refreshed.locator('#moduleDetail').evaluate(node => node.open), false, '刷新释放详情打开状态');
    assert.equal(await page.locator('[data-dashboard-frame]').count(), 1);
    assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(directory, 'data.js'))).digest('hex'), sourceHash,
      '详情与阅读验收不改共享数据文件');
    assert.deepEqual(errors, [], '详情/离线/响应布局零JS异常');
    console.log(JSON.stringify({ result: 'PASS', scope: focused ? 'media-announcements' : 'full-reading-details',
      views: views.length, modes: ['file', 'http', 'offline-share'],
      dataKinds: focused ? ['配图显示边界', '公告原表与原文'] : ['数值原值', '榜单样本', '图文原文', '规划说明'],
      nullAndZero: !focused,
      safeSources: !focused, focusTrapAndReturn: !focused, offlineModalCleanup: !focused, pageErrors: errors.length, layouts }));
  } finally {
    for (const context of contexts) await context.close();
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
