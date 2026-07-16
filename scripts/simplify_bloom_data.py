"""把真實 Bloom 總表精簡成序列分析用的單一乾淨表，並診斷「亂問」學生。

來源：data/Bloom_質性轉量化_分析整理總表.xlsx 的
      06_對照逐題結果 + 07_實驗逐題結果（表頭在第 3 列，header=2）。
輸出：data/Bloom_序列分析_精簡.xlsx（單一工作表，只留序列分析必要欄位）。
另外印出每位學生的提問數與 L0／無效認知比例，供人工判斷是否剔除亂問學生。

用法：
    python scripts/simplify_bloom_data.py
    python scripts/simplify_bloom_data.py --drop 學生A 學生B   # 剔除指定學生後再輸出
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "對話分析", "原始檔", "Bloom_質性轉量化_分析整理總表.xlsx")
OUT = os.path.join(ROOT, "data", "對話分析", "Bloom_序列分析_精簡.xlsx")
SHEETS = ["06_對照逐題結果", "07_實驗逐題結果"]

# 原始欄位 → 精簡欄位
COLMAP = {
    "組別": "組別",
    "CommonUserName": "學生",
    "CUserID": "學生ID",
    "來源列號": "題序",
    "CreateTime": "時間",
    "UserQuestion": "提問",
    "Bloom_Level": "Bloom層級",
    "Bloom_Level_Name": "Bloom層級名稱",
    "Bloom_Score": "Bloom分數",
    "InvolvedKnowledgeLabels": "知識點",
    "KnowledgePointStatus": "K知識點狀態",
    "CorrectnessStatus": "C正確性",
    "RepetitionStatus": "R重複性",
    "Is_Valid_Cognitive": "是否有效認知",
}


def load_clean() -> pd.DataFrame:
    frames = []
    for s in SHEETS:
        raw = pd.read_excel(SRC, sheet_name=s, engine="openpyxl", header=2)
        keep = {k: v for k, v in COLMAP.items() if k in raw.columns}
        df = raw[list(keep)].rename(columns=keep)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    # 去除沒有學生或 Bloom 標記的列
    out = out.dropna(subset=["學生", "Bloom層級"])
    out["題序"] = pd.to_numeric(out["題序"], errors="coerce")
    out = out.sort_values(["組別", "學生", "題序"], kind="stable").reset_index(drop=True)
    return out


def student_diagnostics(df: pd.DataFrame) -> pd.DataFrame:
    """每位學生：提問數、L0 數與比例、無效認知比例（判斷是否亂問）。"""
    g = df.groupby(["組別", "學生"])
    rows = []
    for (grp, stu), sub in g:
        n = len(sub)
        l0 = int((sub["Bloom層級"].astype(str).str.upper() == "L0").sum())
        invalid = (
            int((sub["是否有效認知"] == 0).sum())
            if "是否有效認知" in sub.columns else 0
        )
        rows.append({
            "組別": grp, "學生": stu, "提問數": n,
            "L0數": l0, "L0比例(%)": round(l0 / n * 100, 1),
            "無效認知比例(%)": round(invalid / n * 100, 1),
        })
    return pd.DataFrame(rows).sort_values("L0比例(%)", ascending=False).reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", nargs="*", default=[], help="要剔除的學生名稱")
    args = ap.parse_args(argv)

    df = load_clean()
    print(f"合併後共 {len(df)} 題、學生 {df['學生'].nunique()} 位、組別 {sorted(df['組別'].unique())}")

    diag = student_diagnostics(df)
    print("\n=== 每位學生診斷（依 L0 比例排序）===")
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
