// 图片加载回归：HTTP200 HTML不是有效图片，不能显示成“图片待核对”。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.DNS_PLAYWRIGHT_MODULE || 'playwright');
const base = path.resolve(__dirname, '../看板');
const read = name => fs.readFileSync(path.join(base, '渲染器', name), 'utf8');

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.DNS_BROWSER_EXECUTABLE ? { executablePath: process.env.DNS_BROWSER_EXECUTABLE } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1200, height: 900 } });
    const errors = [], responses = [], requests = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('https://media.fixture.test/**', async route => {
      const url = route.request().url(); requests.push(url);
      const valid = url.endsWith('/valid.png');
      responses.push({ url, status: 200, mime: valid ? 'image/png' : 'text/html' });
      await route.fulfill({ status: 200, contentType: valid ? 'image/png' : 'text/html',
        body: valid ? Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=', 'base64')
          : '<!doctype html><title>404</title><h1>这一页走丢了</h1>' });
    });
    const cases = [
      { id: 'valid', pid: 'P1', img: 'https://media.fixture.test/valid.png' },
      { id: 'failed', pid: 'P2', img: 'https://media.fixture.test/missing.jpg' },
      { id: 'pending', pid: 'P3', img: '媒体/P3/repeated.jpg' },
      { id: 'missing', pid: 'P4', img: '' }
    ];
    const reviews = Object.fromEntries(cases.map(item => [item.pid, { noimg: '暂无配图', items: [{ name: item.id + '文章',
      img: item.img, url: 'https://article.fixture.test/' + item.id, desc: '已保存摘要', date: '11-12' }] }]));
    const cards = cases.map(item => '<div class="card" data-mid="' + item.id + '"><div class="card-top"><span class="t">' + item.id + '</span></div>'
      + '<div class="revcards" data-review="' + item.pid.slice(1) + '"></div></div>'
      + '<a class="focus-item" data-focus-kind="review" data-focus-module="' + item.id + '" data-focus-pid="' + item.pid + '">'
      + '<div class="focus-content"></div><span class="focus-link-label">打开原文</span></a>').join('');
    await page.setContent('<style>.card{width:480px}.rmedia img,.focus-image{width:80px;height:80px}</style><div id="dns-dash">' + cards + '</div>'
      + '<script>var root=document.getElementById("dns-dash"),REVIEWS=' + JSON.stringify(reviews) + ',MEDIA_OMISSIONS=["媒体/P3/repeated.jpg"],charts=[],shareEls=[];</script>'
      + '<script>' + read('04_pager.js') + '</script><script>' + read('70_review.js') + '</script><script>' + read('78_reading.js') + '</script>');
    await page.evaluate(async () => {
      await Promise.all([...document.images].map(async img => { img.loading = 'eager'; try { await img.decode(); } catch {} }));
    });
    await page.waitForFunction(() => document.querySelector('[data-mid="failed"] .rmedia')?.dataset.mediaState === 'load-error'
      && document.querySelector('[data-focus-module="failed"] [data-media-state="load-error"]'));

    for (const item of cases) {
      const card = page.locator('[data-mid="' + item.id + '"]');
      const focus = page.locator('[data-focus-module="' + item.id + '"]');
      const expected = item.id === 'valid' ? 'loaded' : item.id === 'failed' ? 'load-error' : item.id === 'pending' ? 'pending-review' : 'missing';
      assert.equal(await card.locator('.rmedia').getAttribute('data-media-state'), expected, item.id + '模块图片状态');
      assert.equal(await focus.locator('[data-media-state]').getAttribute('data-media-state'), expected, item.id + '精选图片状态');
      assert.equal(await card.locator('a.revcard').getAttribute('href'), 'https://article.fixture.test/' + item.id);
      assert.equal(await focus.getAttribute('href'), 'https://article.fixture.test/' + item.id);
      assert.equal(await card.locator('a.revcard a,a.revcard button').count(), 0, '整卡原文不嵌套交互');
      if (item.id === 'valid') {
        assert.equal(await card.locator('img').evaluate(img => img.complete && img.naturalWidth > 0), true);
        assert.equal(await focus.locator('img').evaluate(img => img.complete && img.naturalWidth > 0), true);
      } else {
        assert.equal(await card.locator('img').count(), 0);
        assert.equal(await focus.locator('img').count(), 0);
      }
      if (item.id === 'failed') {
        assert.equal(await card.locator('.rnoimg').innerText(), '图片暂未加载 · 点击查看原文');
        assert.equal(await focus.locator('.focus-image-placeholder').innerText(), '图片暂未加载 · 点击查看原文');
      }
      if (item.id === 'pending') {
        assert.equal(await card.locator('.rnoimg').innerText(), '图片待核对');
        assert.equal(await focus.locator('.focus-image-placeholder').innerText(), '图片待核对');
      }
    }
    assert.ok(responses.some(response => response.status === 200 && response.mime === 'text/html'));
    assert.ok(!requests.some(url => url.includes('repeated.jpg')), '确认待核对的图片不发起请求');
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ result: 'PASS', contexts: ['模块图文', '首页精选'], cases: cases.map(item => item.id),
      html200Fallback: true, originalLinksRetained: true, pageErrors: errors.length }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
