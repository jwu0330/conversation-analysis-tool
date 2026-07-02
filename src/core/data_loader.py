"""資料上傳與讀取。

支援 Excel（多工作表）與 CSV（自動嘗試常見中文編碼）。
所有函式接受 file-like 物件（例如 Streamlit 的 UploadedFile）或路徑字串，
方便在 UI 與單元測試中重複使用。
"""
from __future__ import annotations

import io
from typing import Any

import pandas as pd

# CSV 常見編碼（優先嘗試含 BOM 的 utf-8，再試繁中常用的 big5）
CSV_ENCODINGS = ["utf-8-sig", "utf-8", "big5", "cp950", "gbk", "latin1"]


def _to_buffer(file: Any) -> Any:
    """把可能被重複讀取的 file-like 物件轉為可 seek 的 BytesIO。"""
    if hasattr(file, "read"):
        data = file.read()
        if isinstance(data, str):
            data = data.encode("utf-8")
        return io.BytesIO(data)
    return file  # 路徑字串


def is_excel(filename: str) -> bool:
    name = (filename or "").lower()
    return name.endswith((".xlsx", ".xls", ".xlsm"))


def get_excel_sheets(file: Any) -> list[str]:
    """回傳 Excel 檔的所有工作表名稱。"""
    buf = _to_buffer(file)
    with pd.ExcelFile(buf, engine="openpyxl") as xls:
        return list(xls.sheet_names)


def load_excel(file: Any, sheet_name: str | int = 0) -> pd.DataFrame:
    """讀取指定工作表為 DataFrame。"""
    buf = _to_buffer(file)
    return pd.read_excel(buf, sheet_name=sheet_name, engine="openpyxl")


def load_csv(file: Any) -> pd.DataFrame:
    """讀取 CSV，自動嘗試多種編碼以支援繁體中文資料。"""
    buf = _to_buffer(file)
    last_err: Exception | None = None
    for enc in CSV_ENCODINGS:
        try:
            if hasattr(buf, "seek"):
                buf.seek(0)
            return pd.read_csv(buf, encoding=enc)
        except (UnicodeDecodeError, UnicodeError) as err:
            last_err = err
            continue
    raise ValueError(f"無法辨識 CSV 編碼，已嘗試 {CSV_ENCODINGS}") from last_err


def load_any(file: Any, filename: str, sheet_name: str | int = 0) -> pd.DataFrame:
    """依副檔名自動選擇讀取方式。"""
    if is_excel(filename):
        return load_excel(file, sheet_name=sheet_name)
    return load_csv(file)
