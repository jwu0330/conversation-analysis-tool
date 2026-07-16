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
# 序列/對話分析用的內建資料來源（量化分析資料另放 data/量化/，由準實驗模組讀取）
# 畫面只列正式資料；sample_data 僅供自動化測試與開發使用。
BUILTIN_DIRS = [os.path.join("data", "對話分析")]
_CN_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

# 預設「實際資料」：網頁一開／重新整理就自動載入這份，免手動上傳。
# 找不到這個檔名時，退而載入掃描到的第一個內建資料。
# 目前預設為「知識點_原始版」（一題一列、不重複，含 Bloom 與 K/C/R 三向度，
# 適合涵蓋度與組間統計）；序列分析可在「內建資料」選單改選序列展開版／類別版。
DEFAULT_DATASET_FILENAME = "知識點_原始版_467.xlsx"


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
            if os.path.basename(path).startswith("~$"):
                continue  # Excel 開啟時產生的鎖定暫存檔，不可列入資料選單
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
                "label": f"資料{num}：{os.path.basename(path)}",
                "path": path,
                "filename": os.path.basename(path),
            }
        )
    return datasets


def load_dataset(path: str) -> pd.DataFrame:
    """讀取內建資料檔為 DataFrame（Excel 取第一個工作表；CSV 自動辨識編碼）。"""
    return data_loader.load_any(path, os.path.basename(path))


def default_dataset_path() -> str | None:
    """回傳預設實際資料的完整路徑。

    只回傳明確指定的預設檔，避免缺檔時靜默分析另一份資料。
    """
    found = discover_datasets()
    if not found:
        return None
    for d in found:
        if d["filename"] == DEFAULT_DATASET_FILENAME:
            return d["path"]
    return None
