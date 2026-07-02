"""描述統計：數值欄位彙總 + 類別欄位次數/比例/累積/排名。"""
from __future__ import annotations

import pandas as pd

# 數值型統計函數註冊表：名稱 -> (中文標籤, 計算函式)
NUMERIC_STATS: dict[str, tuple[str, callable]] = {
    "count": ("總筆數", lambda s: int(s.count())),
    "missing": ("缺漏值數量", lambda s: int(s.isna().sum())),
    "unique": ("不重複值數量", lambda s: int(s.nunique(dropna=True))),
    "sum": ("加總", lambda s: float(s.sum())),
    "mean": ("平均", lambda s: float(s.mean())),
    "median": ("中位數", lambda s: float(s.median())),
    "max": ("最大值", lambda s: float(s.max())),
    "min": ("最小值", lambda s: float(s.min())),
    "std": ("標準差", lambda s: float(s.std(ddof=1))),
    "var": ("變異數", lambda s: float(s.var(ddof=1))),
}


def describe_numeric(series: pd.Series, funcs: list[str] | None = None) -> pd.DataFrame:
    """對數值欄位套用選定的統計函數，回傳兩欄表格（統計量 / 數值）。"""
    if funcs is None:
        funcs = list(NUMERIC_STATS.keys())
    s = pd.to_numeric(series, errors="coerce")
    rows = []
    for key in funcs:
        if key not in NUMERIC_STATS:
            continue
        label, fn = NUMERIC_STATS[key]
        try:
            value = fn(s)
        except (ValueError, TypeError):
            value = float("nan")
        rows.append({"統計量": label, "數值": value})
    return pd.DataFrame(rows)


def frequency_table(series: pd.Series, dropna: bool = True) -> pd.DataFrame:
    """類別欄位的次數表：次數、比例、百分比、累積百分比、排名。"""
    counts = series.value_counts(dropna=dropna)
    total = counts.sum()
    out = pd.DataFrame({"類別": counts.index.astype(str), "次數": counts.values})
    out["比例"] = (out["次數"] / total).round(4) if total else 0.0
    out["百分比(%)"] = (out["次數"] / total * 100).round(2) if total else 0.0
    out["累積百分比(%)"] = out["百分比(%)"].cumsum().round(2)
    out["排名"] = out["次數"].rank(ascending=False, method="min").astype(int)
    return out.reset_index(drop=True)
