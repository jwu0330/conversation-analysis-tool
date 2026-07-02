"""結果匯出：把多個表格寫入單一 Excel 檔（含分析參數紀錄）。"""
from __future__ import annotations

import io

import pandas as pd


def tables_to_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    """把 {工作表名稱: DataFrame} 寫成 Excel 位元組，供 Streamlit 下載。

    工作表名稱會自動截斷至 31 字元（Excel 限制）並移除非法字元。
    """
    buffer = io.BytesIO()
    used: set[str] = set()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for raw_name, frame in sheets.items():
            name = _safe_sheet_name(raw_name, used)
            used.add(name)
            keep_index = isinstance(frame.index, pd.MultiIndex) or frame.index.name is not None
            frame.to_excel(writer, sheet_name=name, index=keep_index)
    buffer.seek(0)
    return buffer.getvalue()


def _safe_sheet_name(name: str, used: set[str]) -> str:
    for ch in "[]:*?/\\":
        name = name.replace(ch, "_")
    name = (name or "Sheet")[:31]
    base, i = name, 1
    while name in used:
        suffix = f"_{i}"
        name = base[: 31 - len(suffix)] + suffix
        i += 1
    return name


def build_params_frame(params: dict) -> pd.DataFrame:
    """把分析參數（檔名、時間、欄位、方法等）整理成兩欄表格。"""
    rows = [{"項目": k, "內容": _stringify(v)} for k, v in params.items()]
    return pd.DataFrame(rows)


def _stringify(value) -> str:
    if isinstance(value, (list, tuple)):
        return "、".join(str(v) for v in value)
    if isinstance(value, dict):
        return "；".join(f"{k}={v}" for k, v in value.items())
    return str(value)
