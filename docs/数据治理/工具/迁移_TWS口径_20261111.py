"""拆分P45混合单位，保留原文件和每一行；不修改任何数值或来源。"""
import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '看板数据固化' / '采集脚本'))
import common

ACTIVE = ROOT / '看板数据固化/CSV数据/行业数据-P45-TWS.csv'
ARCHIVE = ACTIVE.parent / '_归档'
ORIGINAL = ARCHIVE / '行业数据-P45-TWS混合口径原始_20261111.csv'
VOLUME = ARCHIVE / '行业数据-P45-TWS出货量历史.csv'


def split_rows(rows):
    forecast, volume = [], []
    for row in rows:
        unit = row.get('单位', '').strip()
        if unit == '%':
            if 'E' not in row.get('备注', '') and '预测' not in row.get('备注', ''):
                raise ValueError('同比记录未注明实际/预测，需人工核对后迁移')
            forecast.append(row)
        elif unit == '百万台':
            volume.append(row)
        else:
            raise ValueError(f'未知单位，不迁移：{unit!r}')
    if not forecast:
        raise ValueError('没有同比预测记录，不迁移')
    return forecast, volume


def main():
    original_bytes = ORIGINAL.read_bytes() if ORIGINAL.exists() else ACTIVE.read_bytes()
    reader = csv.DictReader(io.StringIO(original_bytes.decode('utf-8-sig')))
    columns, original = reader.fieldnames, list(reader)
    forecast, volume = split_rows(original)
    if sorted(json.dumps(r, sort_keys=True) for r in original) != sorted(
            json.dumps(r, sort_keys=True) for r in forecast + volume):
        raise ValueError('逐行零丢失验证失败')
    if ORIGINAL.exists():
        with ACTIVE.open(encoding='utf-8-sig', newline='') as f:
            active_rows = list(csv.DictReader(f))
        # 已迁移后的采集可以更新预测，不用归档旧值覆盖新值。
        if all(r.get('单位') == '%' for r in active_rows):
            print('P45已拆分；原始归档保留，当前预测不覆写')
            return
        if ACTIVE.read_bytes() != original_bytes:
            raise ValueError('当前混合文件与归档不一致，拒绝覆盖')
    ARCHIVE.mkdir(exist_ok=True)
    if not ORIGINAL.exists():
        ORIGINAL.write_bytes(original_bytes)
    if ORIGINAL.read_bytes() != original_bytes:
        raise ValueError('原文件逐字节归档校验失败')
    if VOLUME.exists():
        with VOLUME.open(encoding='utf-8-sig', newline='') as f:
            if list(csv.DictReader(f)) != volume:
                raise ValueError('历史出货量归档已有不同内容，拒绝覆盖')
    else:
        common.write_csv_atomic(str(VOLUME), columns, volume)
    common.write_csv_atomic(str(ACTIVE), columns, forecast)
    print(f'P45迁移完成：原始{len(original)}行 → 同比预测{len(forecast)}行 + 历史出货量{len(volume)}行；逐行/原文件零丢失')


if __name__ == '__main__':
    main()
