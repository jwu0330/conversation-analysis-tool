"""資料品質檢查：基本摘要、缺漏值、重複資料。"""
from __future__ import annotations

import pandas as pd


def basic_summary(df: pd.DataFrame) -> dict:
    """回傳筆數、欄位數、欄位名稱、記憶體用量。"""
    return {
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "columns": list(df.columns),
        "memory_kb": round(df.memory_usage(deep=True).sum() / 1024, 1),
    }


def missing_report(df: pd.DataFrame) -> pd.DataFrame:
    """每個欄位的缺漏值數量與比例。"""
    n = len(df)
    miss = df.isna().sum()
    out = pd.DataFrame(
        {
            "欄位": miss.index,
            "缺漏數": miss.values,
            "缺漏比例(%)": (miss.values / n * 100).round(2) if n else 0,
        }
    )
    return out.reset_index(drop=True)


def duplicate_report(df: pd.DataFrame) -> dict:
    """完全重複的資料列統計。"""
    dup_mask = df.duplicated(keep="first")
    return {
        "duplicate_rows": int(dup_mask.sum()),
        "duplicate_ratio_pct": round(dup_mask.mean() * 100, 2) if len(df) else 0.0,
    }


def duplicate_rows(df: pd.DataFrame) -> pd.DataFrame:
    """回傳所有重複的資料列（含第一次出現者）以供檢視。"""
    mask = df.duplicated(keep=False)
    return df[mask]
