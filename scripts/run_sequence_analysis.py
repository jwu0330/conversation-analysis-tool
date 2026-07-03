"""Bloom 提問序列分析 — 獨立命令列工具（不需 Streamlit / 不開網頁）。

這支腳本與網頁 App 共用同一份核心邏輯 src/sequence/analysis.py（呼叫 analyze()），
因此對相同輸入與參數，算出的序列、轉移表、GSEQ 統計「必然與網頁一模一樣」。
它的用途是：可重複驗證、批次處理、寫進論文附錄的可執行紀錄。

用法範例：
    python scripts/run_sequence_analysis.py sample_data/conversation_sample.xlsx \
        --student 學生ID --group 組別 --bloom Bloom層級 --order 對話ID \
        --high-min 4 --alpha 0.05 --output 序列分析結果.xlsx

欄位參數可省略，會自動辨識。--exclude-l0 可排除 L0。
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

# 讓腳本能找到 src 套件
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sequence import analysis as seq  # noqa: E402


def load_table(path: str) -> pd.DataFrame:
    """讀 Excel 或 CSV（CSV 自動嘗試常見中文編碼）。"""
    if path.lower().endswith((".xlsx", ".xls", ".xlsm")):
        return pd.read_excel(path, engine="openpyxl")
    for enc in ["utf-8-sig", "utf-8", "big5", "cp950", "gbk"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError("無法辨識 CSV 編碼")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bloom 提問序列分析（獨立 CLI）")
    p.add_argument("input", help="輸入檔（.xlsx / .csv）")
    p.add_argument("--student", help="學生 ID 欄位（省略則自動辨識）")
    p.add_argument("--group", help="組別欄位")
    p.add_argument("--bloom", help="Bloom 層級欄位")
    p.add_argument("--order", help="排序依據欄位（題序/時間）")
    p.add_argument("--high-min", type=int, default=4, help="高階起始 Level（含以上為高階）")
    p.add_argument("--alpha", type=float, default=0.05, help="顯著水準（預設 0.05）")
    p.add_argument("--exclude-l0", action="store_true", help="排除 L0")
    p.add_argument("--output", help="輸出 Excel 路徑（省略則只印在畫面）")
    return p.parse_args(argv)


def resolve_columns(df: pd.DataFrame, args: argparse.Namespace) -> dict[str, str]:
    guess = seq.guess_columns(list(df.columns))
    cols = {
        "student": args.student or guess["student"],
        "group": args.group or guess["group"],
        "bloom": args.bloom or guess["bloom"],
        "order": args.order or guess["order"],
    }
    missing = [k for k, v in cols.items() if v is None or v not in df.columns]
    if missing:
        raise SystemExit(
            f"[錯誤] 下列欄位無法對應：{missing}；請用 --{'/--'.join(missing)} 指定。\n"
            f"可用欄位：{list(df.columns)}"
        )
    return cols


def run(df: pd.DataFrame, cols: dict[str, str], *, high_min: int, alpha: float,
        include_l0: bool) -> dict:
    """呼叫共用核心（與網頁 App 完全相同的計算）。"""
    return seq.analyze(
        df, cols["student"], cols["group"], cols["bloom"], cols["order"],
        include_l0=include_l0, high_min=high_min, alpha=alpha,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    df = load_table(args.input)
    cols = resolve_columns(df, args)
    result = run(
        df, cols, high_min=args.high_min, alpha=args.alpha,
        include_l0=not args.exclude_l0,
    )

    print("=" * 60)
    print("Bloom 提問序列分析（獨立 CLI）")
    print("=" * 60)
    print(f"欄位對應：{cols}")
    print(f"有效提問 {len(result['work'])} 筆、學生 "
          f"{result['work'][seq.STUDENT].nunique()} 位、組別 {result['groups']}、"
          f"出現 Level {['L'+str(v) for v in result['levels']]}")
    print("-" * 60)

    print("\n[轉移表 transitions]")
    print(result["transitions"].to_string(index=False))

    for g in result["groups"]:
        print(f"\n[GSEQ 顯著轉移 — {g}]（只列 |z|>1.96 顯著者）")
        gdf = result["gseq"]
        sig = gdf[(gdf["組別"] == g) & (gdf["顯著"] != "")]
        if sig.empty:
            print("  （無達顯著的轉移）")
        else:
            print(sig.to_string(index=False))

    if args.output:
        sheets = {
            "個人序列": result["sequences"][["學生", "組別", "提問數", "序列字串"]],
            "轉移表": result["transitions"],
            "GSEQ統計": result["gseq"],
            "高低階轉移": result["highlow"],
            "題序剖面": result["profile"],
        }
        for g, mat in result["matrices"].items():
            sheets[f"轉移矩陣_{g}"] = mat.reset_index().rename(columns={"index": "Source"})
        with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
            for name, frame in sheets.items():
                frame.to_excel(writer, sheet_name=name[:31], index=False)
        print(f"\n已輸出：{args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
