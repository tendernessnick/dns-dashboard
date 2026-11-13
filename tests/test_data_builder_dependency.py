"""生成器依赖缺失时，必须在清理媒体和写入data.js之前停止。"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class DataBuilderDependencyTests(unittest.TestCase):
    def test_missing_pillow_preserves_existing_release(self):
        source = Path(__file__).resolve().parents[1] / '看板' / '生成数据.py'
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / '生成数据.py').write_bytes(source.read_bytes())
            (base / 'data.js').write_bytes(b'existing data')
            (base / '媒体').mkdir()
            image = base / '媒体' / 'existing.jpg'
            image.write_bytes(b'existing image')
            script = '''import builtins,runpy,sys
original_import=builtins.__import__
def without_pillow(name,*args,**kwargs):
    if name == 'PIL' or name.startswith('PIL.'):
        raise ImportError('isolated missing dependency')
    return original_import(name,*args,**kwargs)
builtins.__import__=without_pillow
runpy.run_path(sys.argv[1],run_name='__main__')
'''
            result = subprocess.run([sys.executable, '-X', 'utf8', '-c', script, str(base / '生成数据.py')],
                                    capture_output=True, text=True, encoding='utf-8', timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Pillow', result.stderr)
            self.assertIn('构建已停止', result.stderr)
            self.assertEqual((base / 'data.js').read_bytes(), b'existing data')
            self.assertEqual(image.read_bytes(), b'existing image')


if __name__ == '__main__':
    unittest.main()
