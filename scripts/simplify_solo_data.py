"""把 SOLO 總表精簡成序列/統計分析用的單一乾淨表（對應 simplify_bloom_data.py）。

來源：data/對話分析/原始檔/SOLO_質性轉量化_逐題編碼表.xlsx 的
      工作表「10_SOLO逐題量化」（表頭在第 3 列，header=2）。
輸出：data/對話分析/SOLO_序列分析_精簡.xlsx（單一工作表，只留分析必要欄位）。

層級採 SOLO_Score 0–4（P=0、U=1、M=2、R=3、EA=4），數值化後序列分析可直接使用；
同時保留 SOLO 字母（P/U/M/R/EA）與中文名稱供人工判讀。
另印出每位學生的提問數與 P（前結構=無效）比例，供人工判斷是否剔除亂問學生。

用法：
    python scripts/simplify_solo_data.py
    python scripts/simplify_solo_data.py --drop 學生A 學生B   # 剔除指定學生後再輸出
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "對話分析", "原始檔", "SOLO_質性轉量化_逐題編碼表.xlsx")
OUT = os.path.join(ROOT, "data", "對話分析", "SOLO_序列分析_精簡.xlsx")
SHEET = "10_SOLO逐題量化"

# 與 Bloom 正式分析母體一致：排除 4 位高比例無效輸入學生，共 23 題。
EXCLUDED_STUDENTS = ["許晉瑜", "Test1234!s", "郭承武", "林子弘"]

# 原始欄位 → 精簡欄位（欄名刻意對齊 Bloom 精簡檔，讓前端自動辨識學生/組別/層級/題序）
COLMAP = {
    "組別": "組別",
    "CommonUserName": "學生",
    "CUserID": "學生ID",
    "對話順序_學生內": "題序",
    "CreateTime": "時間",
    "UserQuestion": "提問",
    "脈絡還原後問題": "脈絡還原問題",
    "SOLO_Score": "SOLO層級",           # 數值 0–4，序列分析的「層級」欄
    "SOLO_Level": "SOLO字母",           # P/U/M/R/EA
    "SOLO_Level_Name": "SOLO層級名稱",
    "InvolvedKnowledgeLabels": "知識點",
    "KnowledgePointStatus": "K知識點狀態",
    "CorrectnessStatus": "C正確性",
    "RepetitionStatus": "R重複性",
    "Is_Valid_SOLO": "是否有效認知",
    "Is_Relational_or_Higher": "是否關聯以上",
    "Needs_Manual_Review": "需人工複核",
}
# SOLO分數 另存一份（與 SOLO層級同值，但語意上是「分數」，方便統計分析當依變數）
SCORE_FROM = "SOLO_Score"


def load_clean() -> pd.DataFrame:
    raw = pd.read_excel(SRC, sheet_name=SHEET, engine="openpyxl", header=2)
    keep = {k: v for k, v in COLMAP.items() if k in raw.columns}
    df = raw[list(keep)].rename(columns=keep)
    if SCORE_FROM in raw.columns:
        df["SOLO分數"] = pd.to_numeric(raw[SCORE_FROM], errors="coerce")
    # 原始活頁簿這兩欄是 Excel 公式；openpyxl 寫回後公式仍在但快取值可能為空。
    # 依原公式直接由固定 SOLO 分數恢復，避免把空快取誤當缺失。
    df["是否有效認知"] = (df["SOLO分數"] > 0).astype(int)
    df["是否關聯以上"] = (df["SOLO分數"] >= 3).astype(int)
    # 去除沒有學生或 SOLO 層級的列
    df = df.dropna(subset=["學生", "SOLO層級"])
    df = df[~df["學生"].isin(EXCLUDED_STUDENTS)]
    df["SOLO層級"] = pd.to_numeric(df["SOLO層級"], errors="coerce").astype("Int64")
    df["題序"] = pd.to_numeric(df["題序"], errors="coerce")
    df = df.dropna(subset=["SOLO層級", "題序"])
    df["題序"] = df["題序"].astype(int)
    df["SOLO層級"] = df["SOLO層級"].astype(int)
    df = df.sort_values(["組別", "學生", "題序"], kind="stable").reset_index(drop=True)
    return df


def student_diagnostics(df: pd.DataFrame) -> pd.DataFrame:
    """每位學生：提問數、P（前結構=無效）數與比例、無效認知比例（判斷是否亂問）。"""
    rows = []
    for (grp, stu), sub in df.groupby(["組別", "學生"]):
        n = len(sub)
        p0 = int((sub["SOLO層級"] == 0).sum())
        invalid = (
            int((sub["是否有效認知"] == 0).sum())
            if "是否有效認知" in sub.columns else 0
        )
        rows.append({
            "組別": grp, "學生": stu, "提問數": n,
            "P(前結構)數": p0, "P比例(%)": round(p0 / n * 100, 1),
            "無效認知比例(%)": round(invalid / n * 100, 1),
        })
    return pd.DataFrame(rows).sort_values("P比例(%)", ascending=False).reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", nargs="*", default=[], help="除正式排除名單外，額外剔除的學生名稱")
    args = ap.parse_args(argv)

    df = load_clean()
    dist = df["SOLO層級"].value_counts().sort_index().to_dict()
    print(f"合併後共 {len(df)} 題、學生 {df['學生'].nunique()} 位、組別 {sorted(df['組別'].unique())}")
    print(f"SOLO 層級分布（0=P,1=U,2=M,3=R,4=EA）：{dist}")

    diag = student_diagnostics(df)
    print("\n=== 每位學生診斷（依 P 比例排序）===")
    print(diag.to_string(index=False))

    if args.drop:
        before = df["學生"].nunique()
        df = df[~df["學生"].isin(args.drop)].reset_index(drop=True)
        print(f"\n已剔除 {args.drop}：學生 {before} → {df['學生'].nunique()} 位、剩 {len(df)} 題")

    df.to_excel(OUT, index=False, engine="openpyxl")
    print(f"\n已輸出精簡檔：{OUT}（{df.shape[0]} 列 × {df.shape[1]} 欄）")
    print(f"欄位：{list(df.columns)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
