import csv
import importlib.util
import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('tws_migration', ROOT / 'docs/数据治理/工具/迁移_TWS口径_20261111.py')
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


class TwsMigrationTests(unittest.TestCase):
    def test_original_rows_survive_in_the_two_separate_unit_sets(self):
        with MIGRATION.ORIGINAL.open(encoding='utf-8-sig', newline='') as f:
            original = list(csv.DictReader(f))
        forecast, volume = MIGRATION.split_rows(original)
        self.assertEqual(len(original), len(forecast) + len(volume))
        self.assertEqual({r['单位'] for r in forecast}, {'%'})
        self.assertEqual({r['单位'] for r in volume}, {'百万台'})
        with MIGRATION.ACTIVE.open(encoding='utf-8-sig', newline='') as f:
            self.assertEqual(list(csv.DictReader(f)), forecast)
        with MIGRATION.VOLUME.open(encoding='utf-8-sig', newline='') as f:
            self.assertEqual(list(csv.DictReader(f)), volume)

    def test_unknown_unit_is_not_silently_discarded(self):
        with self.assertRaises(ValueError):
            MIGRATION.split_rows([{'单位': '千台', '数值': '300'}])

    def test_unclassified_growth_is_not_labelled_a_forecast(self):
        with self.assertRaises(ValueError):
            MIGRATION.split_rows([{'单位': '%', '数值': '3', '备注': ''}])


if __name__ == '__main__':
    unittest.main()
