"""把逐題 K/C/R 編碼整理成可進行組間比較的學生層級指標。"""
from __future__ import annotations

import pandas as pd


METRIC_LABELS = {
    "K": "K：知識點層級平均（0 無／1 單一／2 多個）",
    "C": "C：正確提問率（Correct=1／Incorrect=0）",
    "R": "R：重複提問率（Repeated=1／New=0）",
}


def _first_column(df: pd.DataFrame, names: list[str]) -> str | None:
    return next((name for name in names if name in df.columns), None)


def student_metrics(
    df: pd.DataFrame,
    student_col: str | None = None,
    group_col: str | None = None,
) -> pd.DataFrame:
    """回傳每位學生一列的組別與 K/C/R 平均值；無法判定者保留缺值。"""
    student = student_col or _first_column(df, ["學生ID", "學生", "student_id", "student"])
    group = group_col or _first_column(df, ["組別", "group", "Group"])
    if student is None or group is None:
        return pd.DataFrame(columns=["學生", "組別", "K", "C", "R"])

    out = pd.DataFrame({"學生": df[student], "組別": df[group]})

    k_col = _first_column(df, ["K知識點狀態", "K"])
    k_count = _first_column(df, ["知識點數"])
    if k_col:
        k_text = df[k_col].astype("string").str.strip().str.lower()
        out["K"] = k_text.map({
            "沒有知識點": 0.0, "none": 0.0, "zero": 0.0, "0": 0.0,
            "single": 1.0, "單一": 1.0, "一個知識點": 1.0, "1": 1.0,
            "multiple": 2.0, "多個": 2.0, "多個知識點": 2.0, "2": 2.0,
        })
    else:
        out["K"] = pd.NA
    if k_count:
        count_score = pd.to_numeric(df[k_count], errors="coerce").clip(0, 2)
        out["K"] = pd.to_numeric(out["K"], errors="coerce").fillna(count_score)

    c_col = _first_column(df, ["C正確性", "C"])
    if c_col:
        c_text = df[c_col].astype("string").str.strip().str.lower()
        out["C"] = c_text.map({
            "correct": 1.0, "正確": 1.0, "1": 1.0,
            "incorrect": 0.0, "錯誤": 0.0, "0": 0.0,
        })
    else:
        out["C"] = pd.NA

    r_col = _first_column(df, ["R重複性", "R"])
    if r_col:
        r_text = df[r_col].astype("string").str.strip().str.lower()
        out["R"] = r_text.map({
            "repeated": 1.0, "重複": 1.0, "1": 1.0,
            "new": 0.0, "未重複": 0.0, "新提問": 0.0, "0": 0.0,
        })
    else:
        out["R"] = pd.NA

    out = out.dropna(subset=["學生", "組別"])
    return out.groupby(["學生", "組別"], as_index=False)[["K", "C", "R"]].mean()
