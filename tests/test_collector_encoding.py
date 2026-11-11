"""Windows系统编码不可影响采集成功/失败的机器可读状态。"""
import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '看板数据固化/采集脚本'
sys.path.insert(0, str(SCRIPTS))
import run_all


class CollectorEncodingTests(unittest.TestCase):
    def test_child_status_is_utf8_even_if_parent_environment_requests_gbk(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / 'collect_P999_编码.py'
            script.write_text("print(('成功', '中文详情', 0.1))\n", encoding='utf-8')
            with patch.object(run_all, 'HERE', temp), \
                    patch.object(run_all, '_lock_acquire', return_value=str(Path(temp) / 'lock')), \
                    patch.object(run_all.common, 'begin_run', return_value='encoding_test'), \
                    patch.object(run_all, 'write_state') as state, \
                    patch.object(run_all, 'write_news_health'), \
                    patch.object(run_all.time, 'sleep'), \
                    patch.object(sys, 'argv', ['run_all.py', 'P999']), \
                    patch.dict(os.environ, {'PYTHONIOENCODING': 'cp936'}), \
                    contextlib.redirect_stdout(io.StringIO()):
                run_all.main()
            self.assertEqual(state.call_args.args[2:5], (1, 0, 0))
            result = state.call_args.args[5][0]
            self.assertEqual(result[2:4], ('成功', '中文详情'))


if __name__ == '__main__':
    unittest.main()
