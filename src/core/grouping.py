"""分組比較與交叉表。"""
from __future__ import annotations

import pandas as pd

# 分組聚合可用的函數
GROUP_AGGS: dict[str, str] = {
    "count": "次數",
    "sum": "加總",
    "mean": "平均",
    "median": "中位數",
    "std": "標準差",
    "min": "最小值",
    "max": "最大值",
}


def crosstab(
    df: pd.DataFrame,
    row: str,
    col: str,
    normalize: str | bool = False,
    margins: bool = True,
) -> pd.DataFrame:
    """建立兩個類別欄位的交叉表。

    normalize: False=次數, "index"=列百分比, "columns"=欄百分比, "all"=總百分比
    """
    ct = pd.crosstab(
        df[row],
        df[col],
        normalize=normalize,
        margins=margins,
        margins_name="合計",
    )
    if normalize:
        ct = (ct * 100).round(2)
    return ct


def group_aggregate(
    df: pd.DataFrame,
    group_cols: list[str],
    value_col: str,
    aggs: list[str],
) -> pd.DataFrame:
    """依分組欄位對某數值欄位計算多種聚合統計。"""
    valid = [a for a in aggs if a in GROUP_AGGS]
    grouped = df.groupby(group_cols)[value_col].agg(valid)
    if isinstance(grouped, pd.Series):
        grouped = grouped.to_frame()
    grouped = grouped.rename(columns={a: GROUP_AGGS[a] for a in valid})
    return grouped.reset_index()


def group_frequency(
    df: pd.DataFrame,
    group_col: str,
    category_col: str,
    as_percentage: bool = False,
) -> pd.DataFrame:
    """依組別統計某類別欄位的次數（或組內百分比），長格式方便繪圖。"""
    grp = (
        df.groupby([group_col, category_col]).size().reset_index(name="次數")
    )
    if as_percentage:
        totals = grp.groupby(group_col)["次數"].transform("sum")
        grp["百分比(%)"] = (grp["次數"] / totals * 100).round(2)
    return grp
