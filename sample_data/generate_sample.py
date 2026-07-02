"""產生符合情境的模擬對話紀錄資料，供開發與 demo 使用。

執行：
    python sample_data/generate_sample.py

會輸出 conversation_sample.xlsx 與 conversation_sample.csv 到本目錄。
使用固定亂數種子，確保結果可重複。
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)

N_STUDENTS = 40          # 每組 20 人
DIALOGS_PER_STUDENT = 8  # 每人前後測各 4 筆左右

KNOWLEDGE_POINTS = [
    "變數與資料型態", "迴圈", "條件判斷", "函式", "陣列", "字典", "遞迴", "例外處理",
]
QUESTION_TYPES = ["事實型", "理解型", "應用型", "分析型", "評鑑型", "創造型"]


def _bloom_level(group: str, timepoint: str) -> int:
    """實驗組在後測較容易出現高階層級（模擬處理效果）。"""
    if group == "實驗組" and timepoint == "後測":
        weights = [0.08, 0.12, 0.20, 0.28, 0.20, 0.12]
    elif group == "實驗組":
        weights = [0.18, 0.22, 0.25, 0.18, 0.10, 0.07]
    elif timepoint == "後測":
        weights = [0.16, 0.22, 0.26, 0.18, 0.12, 0.06]
    else:
        weights = [0.22, 0.26, 0.24, 0.15, 0.09, 0.04]
    return int(RNG.choice([1, 2, 3, 4, 5, 6], p=weights))


def build() -> pd.DataFrame:
    rows = []
    dialog_id = 1
    for sid in range(1, N_STUDENTS + 1):
        group = "實驗組" if sid <= N_STUDENTS // 2 else "對照組"
        cls = f"{((sid - 1) % 4) + 1}班"
        for timepoint in ["前測", "後測"]:
            for _ in range(DIALOGS_PER_STUDENT // 2):
                level = _bloom_level(group, timepoint)
                solo = min(5, max(1, level - RNG.integers(0, 2)))
                score = float(np.clip(RNG.normal(60 + level * 5, 10), 0, 100).round(1))
                rows.append(
                    {
                        "對話ID": f"D{dialog_id:04d}",
                        "學生ID": f"S{sid:03d}",
                        "組別": group,
                        "班級": cls,
                        "時間點": timepoint,
                        "提問類型": QUESTION_TYPES[level - 1],
                        "Bloom層級": f"Level {level}",
                        "SOLO層級": f"SOLO {solo}",
                        "知識點": RNG.choice(KNOWLEDGE_POINTS),
                        "分數": score,
                    }
                )
                dialog_id += 1
    return pd.DataFrame(rows)


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    df = build()
    xlsx_path = os.path.join(here, "conversation_sample.xlsx")
    csv_path = os.path.join(here, "conversation_sample.csv")
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"已產生 {len(df)} 筆：")
    print(f"  {xlsx_path}")
    print(f"  {csv_path}")


if __name__ == "__main__":
    main()
