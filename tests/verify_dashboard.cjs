// 本地页面与单文件版回归。先重建，再用 DNS_PLAYWRIGHT_MODULE 指定已有 playwright 包（或本地安装）。
// 可选 DNS_BROWSER_EXECUTABLE 指定浏览器，DNS_REVIEW_OUTPUT 指定截图目录。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.DNS_PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const shellDir = path.join(root, '看板');

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.DNS_BROWSER_EXECUTABLE ? { executablePath: process.env.DNS_BROWSER_EXECUTABLE } : {}) });
  const errors = [];
  const pages = [];
  try {
    for (const filename of ['index.html', '数据看板-单文件版.html']) {
      const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
      pages.push(page);
      page.on('pageerror', e => errors.push(`${filename}: ${e.message}`));
      await page.goto(pathToFileURL(path.join(shellDir, filename)).href, { waitUntil: 'load' });
      const period = page.locator('.pctl button[data-m="3"]');
      await period.focus();
      await page.keyboard.press('Enter');
      assert.equal(await page.evaluate(() => PSEL.months), 3, '周期选择支持键盘');
      assert.equal(await period.getAttribute('aria-pressed'), 'true');
      await page.locator('.pctl button').first().click();
      assert.equal(await page.evaluate(() => PSEL), null);
      const tws = page.locator('.card[data-k="45"]');
      assert.match(await tws.innerText(), /同比.*预测/);
      const forecastYear = await page.evaluate(() => getSeries('P45').rows.at(-1)[0].slice(0, 4));
      assert.ok((await tws.innerText()).includes(forecastYear + 'E'));
      assert.equal(await tws.locator('.chart,.sparkrow,.dpill').count(), 0, '预测卡不绘制混合历史或相减');
      const replacement = page.locator('.card[data-k="43"]');
      assert.match(await replacement.innerText(), /年预测/);
      assert.equal(await replacement.locator('.chart,.sparkrow,.dpill').count(), 0);
      const air = page.locator('.card[data-k="38"]');
      const airText = await air.innerText();
      const latest = await page.evaluate(() => getSeries('P38').rows.at(-1)[0].slice(0, 7));
      assert.ok(airText.includes(latest), 'CTK副标题与当前值同一期');
      assert.ok(!airText.includes('载货率46.0%'));
      const tabButtons = page.locator('[data-cotab]');
      assert.equal(await tabButtons.count(), 5);
      for (let i = 0; i < 5; i++) {
        await tabButtons.nth(i).click();
        const card = page.locator('[data-copanel]:not([hidden]) .card[data-change="none"]').first();
        assert.match(await card.innerText(), /年初累计|年初至报告期累计/);
        assert.equal(await card.locator('.dpill').count(), 0);
        const chart = card.locator('.chart').first();
        const box = await chart.boundingBox();
        assert.ok(box && box.width > 100);
        await page.mouse.move(box.x + box.width * 0.75, box.y + box.height * 0.4);
        assert.ok(!(await chart.locator('.ctool').innerText()).includes('较前期'));
      }
      await page.locator('#provbtn').click();
      const cpiDate = await page.evaluate(() => {
        const valid = DDATA.P2.rows.filter(r => r[1] != null);
        return valid.at(-1)[0];
      });
      const cpiRow = page.locator('#prov-P2');
      assert.ok((await cpiRow.innerText()).includes(cpiDate), '附录使用同比最后有效期');
      await page.locator('#pfQ').fill('TWS');
      assert.ok(await page.locator('#provRows tr').count() > 0);
      assert.match(await page.locator('#provRows').innerText(), /TWS/i, '溯源搜索仍可定位词条');
      await page.locator('#pfQ').fill('');
      assert.equal(await page.locator('.vrf').filter({ hasText: '✓核验' }).count(), 0);
      const warningWithoutData = await page.evaluate(() => {
        DDATA._verify.P99999 = { s: 'warn', t: '资讯异常', d: '11-11' };
        const text = freshHTML('P99999');
        delete DDATA._verify.P99999;
        return text;
      });
      assert.ok(warningWithoutData.includes('资讯异常'), '无数据时仍显示异常，不能隐藏坏输入');
      for (const pid of ['P16', 'P20']) {
        const expected = await page.evaluate(pid => CAL[pid].时间线.length, pid);
        const actual = await page.locator(`[data-cal="${pid}"] li`).count();
        assert.equal(actual, expected, '最后一个渲染器仍正常执行');
      }
      await page.evaluate(() => scrollTo(0, document.getElementById('m4').getBoundingClientRect().top + scrollY - 100));
      await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
      assert.equal(await page.locator('#dnav [aria-current="location"]').getAttribute('href'), '#m4');
      await page.evaluate(() => scrollTo(0, 0));
      await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
      assert.equal(await page.locator('#dnav [aria-current="location"]').getAttribute('href'), '#m1', '回到速览后导航不残留旧板块');
      if (process.env.DNS_REVIEW_OUTPUT) {
        fs.mkdirSync(process.env.DNS_REVIEW_OUTPUT, { recursive: true });
        await tws.screenshot({ path: path.join(process.env.DNS_REVIEW_OUTPUT, filename + '-tws.png') });
      }
    }
    const payload = page => page.evaluate(() => JSON.stringify({ data: DDATA, news: NEWS, tops: TOPS, cal: CAL, bind: BIND }));
    assert.equal(await payload(pages[0]), await payload(pages[1]), '本机版与单文件版数据一致');
    const js = fs.readFileSync(path.join(shellDir, 'data.js'), 'utf8');
    const single = fs.readFileSync(path.join(shellDir, '数据看板-单文件版.html'), 'utf8');
    const media = [...js.matchAll(/"(媒体\/[^"\n]+\.jpg)"/g)].map(m => m[1]);
    for (const relative of media) {
      const file = path.join(shellDir, relative);
      assert.ok(fs.existsSync(file), '媒体引用必须存在：' + relative);
      assert.ok(single.includes(fs.readFileSync(file).toString('base64')), '分享版包含同一图片');
    }
    assert.ok(!/"媒体\/[^"\n]+\.jpg"/.test(single), '分享版不依赖本地媒体目录');
    const responsive = [];
    for (const width of [320, 390, 768, 1024, 1366, 1440, 1920]) {
      await pages[0].setViewportSize({ width, height: 1000 });
      await pages[0].evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
      const actual = await pages[0].evaluate(() => document.documentElement.scrollWidth);
      assert.ok(actual <= width + 1, `主体不能横向溢出：${width}px视口，${actual}px文档`);
      responsive.push({ viewport: width, document: actual });
    }
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ result: 'PASS', pages: 2, companies: 5, media: media.length, pageErrors: errors.length, responsive }));
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
