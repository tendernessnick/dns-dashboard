# -*- coding: utf-8 -*-
"""离线部门分享回归：仅使用临时目录，不读取生产数据、不联网。

python -m unittest discover -s tests -p test_department_packaging.py -v
浏览器用例在本地Node/Playwright/Chrome可用时自动运行，否则跳过。
"""
import base64
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


SOURCE = pathlib.Path(__file__).resolve().parents[1] / '看板' / '打包单文件.py'
SPEC = importlib.util.spec_from_file_location('department_packaging_under_test', SOURCE)
pack = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pack)
PAGES = [{'ID': 'strategy', '名称': '战略部', '文件': 'index.html'},
         {'ID': 'marketing', '名称': '市场部', '文件': 'marketing.html'}]
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.base = pathlib.Path(self.temp)
        (self.base / '媒体' / 'P41').mkdir(parents=True)
        (self.base / '媒体' / 'P41' / '照片1.png').write_bytes(PNG)
        self.data = ('const DDATA={name:"中文数据",img:"媒体/P41/照片1.png",'
                     'again:"媒体/P41/照片1.png",remote:"https://example.invalid/amazon.jpg"};')
        (self.base / 'data.js').write_text(self.data, encoding='utf-8')
        for page in PAGES:
            html = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                    '<title>' + page['名称'] + '</title></head><body>'
                    '<a id="to-strategy" data-dashboard-page="strategy" href="index.html">战略</a>'
                    '<a id="to-marketing" data-dashboard-page="marketing" href="marketing.html">市场</a>'
                    '<a id="local-anchor" href="#target">本页锚点</a>'
                    '<a id="bad-page" data-dashboard-page="https://example.invalid/" href="https://example.invalid/">未知</a>'
                    '<div id="duplicate-id">' + page['名称'] + '</div><div id="target">目标</div>'
                    '<script src="data.js"></script><script>'
                    'window.INITS=(window.INITS||0)+1;window.CHECK=DDATA.name;'
                    'var img=document.createElement("img");img.id="photo";img.src=DDATA.img;document.body.appendChild(img);'
                    '</script></body></html>')
            (self.base / page['文件']).write_text(html, encoding='utf-8')

    def build(self):
        return pack.build_bundle(base=self.base, default_id='strategy', pages=PAGES)

    def payload(self):
        source = (self.base / pack.OUTPUT_NAME).read_text(encoding='utf-8')
        match = re.search(r'<script type="application/json" id="dashboard-bundle">(.*?)</script>', source, re.S)
        self.assertIsNotNone(match)
        return json.loads(match[1]), source

    def test_embeds_two_isolated_documents_and_shared_data_only_once(self):
        report = self.build()
        payload, source = self.payload()
        data = base64.b64decode(payload['data']).decode('utf-8')
        self.assertEqual(report['部门数'], 2)
        self.assertEqual(report['媒体数'], 1)
        self.assertEqual([page['id'] for page in payload['pages']], ['strategy', 'marketing'])
        self.assertIn('data:image/png;base64,', data)
        self.assertNotIn('媒体/P41/', data)
        self.assertIn('https://example.invalid/amazon.jpg', data)
        for page in payload['pages']:
            html = base64.b64decode(page['html']).decode('utf-8')
            self.assertIn('id="duplicate-id"', html)
            self.assertNotIn('data:image/png;base64,', html)
        self.assertEqual(source.count(payload['data']), 1)
        self.assertIn('data-dashboard-frame', source)
        self.assertNotIn('postMessage', source)

    def test_missing_registered_page_preserves_previous_share(self):
        old = self.base / pack.OUTPUT_NAME
        old.write_bytes(b'previous-good-release')
        (self.base / 'marketing.html').unlink()
        with self.assertRaises(FileNotFoundError):
            self.build()
        self.assertEqual(old.read_bytes(), b'previous-good-release')

    def test_missing_media_preserves_previous_share(self):
        old = self.base / pack.OUTPUT_NAME
        old.write_bytes(b'previous-good-release')
        (self.base / '媒体' / 'P41' / '照片1.png').unlink()
        with self.assertRaisesRegex(FileNotFoundError, '媒体缺失'):
            self.build()
        self.assertEqual(old.read_bytes(), b'previous-good-release')

    def test_page_without_data_script_is_rejected(self):
        (self.base / 'marketing.html').write_text('<html><body>不完整页面</body></html>', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'data.js引用缺失'):
            self.build()
        self.assertFalse((self.base / pack.OUTPUT_NAME).exists())

    def test_media_path_cannot_escape_media_directory(self):
        (self.base / 'data.js').write_text('var x="媒体/../../private.png";', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '越出媒体目录'):
            self.build()
        self.assertFalse((self.base / pack.OUTPUT_NAME).exists())

    def test_payload_and_data_cannot_terminate_the_script_element(self):
        pages = [dict(page) for page in PAGES]
        pages[1]['名称'] = '市场</script><script>不执行</script>'
        (self.base / 'data.js').write_text('const DDATA={name:"</ScRiPt><script>不执行</script>"};', encoding='utf-8')
        pack.build_bundle(base=self.base, default_id='strategy', pages=pages)
        payload, source = self.payload()
        self.assertEqual(payload['pages'][1]['name'], pages[1]['名称'])
        decoded = base64.b64decode(payload['data']).decode('utf-8')
        self.assertNotRegex(decoded, re.compile(r'</script', re.I))
        self.assertIn('<\\/ScRiPt>', decoded)
        self.assertNotIn('<script>不执行</script>', source)

    def test_atomic_replace_failure_keeps_previous_release_and_cleans_temporary_file(self):
        old = self.base / pack.OUTPUT_NAME
        old.write_bytes(b'previous-good-release')
        with mock.patch.object(pack.os, 'replace', side_effect=PermissionError('mock文件占用')):
            with self.assertRaises(PermissionError):
                self.build()
        self.assertEqual(old.read_bytes(), b'previous-good-release')
        self.assertEqual(list(self.base.glob('*.tmp')), [])

    def test_configuration_loader_is_used_for_default_cli_inputs(self):
        with mock.patch.object(pack, '_load_page_registry', return_value=('strategy', PAGES)) as load:
            report = pack.build_bundle(base=self.base)
        self.assertEqual(report['部门数'], 2)
        load.assert_called_once_with(self.base)

    def test_offline_browser_switch_refresh_history_and_anchors(self):
        node = shutil.which('node')
        module = os.environ.get('DNS_PLAYWRIGHT_MODULE') or str(
            pathlib.Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')
        chrome = os.environ.get('DNS_CHROME_EXECUTABLE') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        if not node or not pathlib.Path(module).exists() or not pathlib.Path(chrome).is_file():
            self.skipTest('本地Node/Playwright/Chrome不可用')
        self.build()
        script = r"""
const {chromium}=require(process.argv[2]);
const assert=require('assert/strict');
const fs=require('fs'),{fileURLToPath}=require('url');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.argv[3]});
  try{
    const context=await browser.newContext({offline:true});
    const page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    const frame=()=>page.frameLocator('[data-dashboard-frame]');
    const expectName=async(name)=>{
      await frame().locator('#duplicate-id').filter({hasText:name}).waitFor();
      assert.equal(await frame().locator('#duplicate-id').innerText(),name);
      assert.equal(await frame().locator('#photo').getAttribute('src').then(x=>x.startsWith('data:image/png;base64,')),true);
      assert.equal(await frame().locator('body').evaluate(()=>window.INITS),1);
      assert.equal(await frame().locator('body').evaluate(()=>window.CHECK),'中文数据');
      assert.equal(await page.locator('[data-dashboard-frame]').getAttribute('title'),name+' · 数据看板');
    };
    await page.goto(process.argv[1]);await expectName('战略部');
    await frame().locator('#to-marketing').click();await expectName('市场部');
    assert.equal(new URL(page.url()).hash,'#page=marketing');
    await frame().locator('#to-strategy').click();await expectName('战略部');
    await page.goBack();await expectName('市场部');
    await page.goForward();await expectName('战略部');
    await frame().locator('#to-marketing').click();await expectName('市场部');
    await page.reload();await expectName('市场部');
    await frame().locator('#local-anchor').click();
    assert.equal(await frame().locator('#target').innerText(),'目标');
    assert.equal(page.frames().find(f=>f.parentFrame()).url(),'about:srcdoc#target');
    assert.equal(await frame().locator('#bad-page').getAttribute('href').then(x=>new URL(x).hash),'#page=strategy');
    await page.goto(process.argv[1]+'#page='+encodeURIComponent('https://example.invalid/'));
    await expectName('战略部');
    await page.goto(process.argv[1]+'#page=__proto__');await expectName('战略部');
    // HTTP同样走浏览器路由，但所有响应在本地mock，不访问网络。
    await context.route('http://dashboard.test/**',route=>route.fulfill({
      status:200,contentType:'text/html; charset=utf-8',
      body:fs.readFileSync(fileURLToPath(process.argv[1]),'utf8')
    }));
    await page.goto('http://dashboard.test/offline.html#page=marketing');await expectName('市场部');
    await frame().locator('#to-strategy').click();await expectName('战略部');
    assert.equal(page.url(),'http://dashboard.test/offline.html#page=strategy');
    assert.equal(errors.length,0,JSON.stringify(errors));
    console.log('offline-browser-ok');
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
"""
        result = subprocess.run([node, '-e', script, (self.base / pack.OUTPUT_NAME).as_uri(), module, chrome],
                                capture_output=True, text=True, encoding='utf-8', timeout=55)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('offline-browser-ok', result.stdout)


if __name__ == '__main__':
    unittest.main()
