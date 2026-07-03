"""內建資料集探索：自動掃描 sample_data/ 與 data/ 底下的檔案。

使用者把整理好的 Excel/CSV 放進 data/ 資料夾，就會自動出現在「內建資料」選單
（測試資料一、二、三…），同時仍保留手動上傳功能。
"""
from __future__ import annotations

import glob
import os

import pandas as pd

from src.core import data_loader

# 專案根目錄（本檔位於 src/datasets.py）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILTIN_DIRS = ["sample_data", "data"]  # 掃描順序（sample_data 為測試資料一）
_CN_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def discover_datasets() -> list[dict]:
    """回傳內建資料清單：[{label, path, filename}]。

    同名的 .xlsx 與 .csv 只留一個（優先 .xlsx），避免同一份資料重複出現。
    """
    picked: dict[tuple[str, str], str] = {}
    order: list[tuple[str, str]] = []
    for sub in BUILTIN_DIRS:
        folder = os.path.join(PROJECT_ROOT, sub)
        if not os.path.isdir(folder):
            continue
        files = sorted(
            glob.glob(os.path.join(folder, "*.xlsx"))
            + glob.glob(os.path.join(folder, "*.xls"))
            + glob.glob(os.path.join(folder, "*.csv"))
        )
        for path in files:
            stem = os.path.splitext(os.path.basename(path))[0]
            key = (sub, stem)
            is_excel = data_loader.is_excel(path)
            # 優先 Excel；若已存在且新的是 csv 則略過
            if key in picked and not is_excel:
                continue
            if key not in picked:
                order.append(key)
            picked[key] = path

    datasets: list[dict] = []
    for i, key in enumerate(order):
        path = picked[key]
        num = _CN_NUM[i] if i < len(_CN_NUM) else str(i + 1)
        datasets.append(
            {
                "label": f"測試資料{num}：{os.path.basename(path)}",
                "path": path,
                "filename": os.path.basename(path),
            }
        )
    return datasets


def load_dataset(path: str) -> pd.DataFrame:
    """讀取內建資料檔為 DataFrame（Excel 取第一個工作表；CSV 自動辨識編碼）。"""
    return data_loader.load_any(path, os.path.basename(path))
