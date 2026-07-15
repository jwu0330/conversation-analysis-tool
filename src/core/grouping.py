"""交叉表（供「敘述性統計 → 交叉熱力圖」使用）。"""
from __future__ import annotations

import pandas as pd


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
