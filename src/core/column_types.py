"""欄位型態自動辨識：類別 / 數值 / 文字 / 日期時間。"""
from __future__ import annotations

import pandas as pd

CATEGORICAL = "categorical"
NUMERIC = "numeric"
TEXT = "text"
DATETIME = "datetime"

TYPE_LABELS_ZH = {
    CATEGORICAL: "類別",
    NUMERIC: "數值",
    TEXT: "文字",
    DATETIME: "日期時間",
}


def infer_column_type(series: pd.Series, cat_max_unique: int = 20) -> str:
    """判斷單一欄位的型態。

    規則：
    - 數值 dtype → 數值
    - 日期時間 dtype → 日期時間
    - 其餘依不重複值數量判斷：少於門檻或重複率高 → 類別，否則視為文字
    """
    s = series.dropna()
    if len(s) == 0:
        return TEXT
    if pd.api.types.is_bool_dtype(s):
        return CATEGORICAL
    if pd.api.types.is_numeric_dtype(s):
        return NUMERIC
    if pd.api.types.is_datetime64_any_dtype(s):
        return DATETIME

    nunique = s.nunique()
    ratio = nunique / len(s)
    if nunique <= cat_max_unique or ratio < 0.5:
        return CATEGORICAL
    return TEXT


def infer_types(df: pd.DataFrame, cat_max_unique: int = 20) -> dict[str, str]:
    """回傳 {欄位名稱: 型態} 對照表。"""
    return {col: infer_column_type(df[col], cat_max_unique) for col in df.columns}


def columns_by_type(df: pd.DataFrame, wanted: str, cat_max_unique: int = 20) -> list[str]:
    """取出符合指定型態的欄位清單。"""
    types = infer_types(df, cat_max_unique)
    return [col for col, t in types.items() if t == wanted]


def categorical_columns(df: pd.DataFrame) -> list[str]:
    """可用於分組/交叉的欄位（類別 + 日期時間）。"""
    types = infer_types(df)
    return [c for c, t in types.items() if t in (CATEGORICAL, DATETIME)]


def numeric_columns(df: pd.DataFrame) -> list[str]:
    return columns_by_type(df, NUMERIC)
