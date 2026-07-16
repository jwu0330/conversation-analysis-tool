# -*- coding: utf-8 -*-
"""由「知識點_序列展開版.xlsx」產生「知識點_類別序列展開版.xlsx」。

作法（完全沿用既有序列展開結果，只加類別欄、重排欄位）：
  1. 讀入 知識點_序列展開版.xlsx（683 列，一題多知識點已各自展開成一列）。
  2. 依 15 個個別知識點對應到 4 大類，新增：
       - 知識點類別   （文字，如「檔案傳輸類」）
       - 知識點類別碼 （整數 1–4；供序列分析頁當「節點欄」直接使用）
  3. 重排欄位順序、輸出新檔。

序列展開邏輯不變：同一題涉及 N 個知識點 → N 列，每列各自帶正確的知識點與類別。
序列分析頁用法：節點欄選「知識點類別碼」＝以類別為單位；選「知識點層級」＝以個別知識點為單位。
"""
from __future__ import annotations
import os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "對話分析", "知識點_序列展開版.xlsx")
OUT = os.path.join(ROOT, "data", "對話分析", "知識點_類別序列展開版.xlsx")

# 15 個別知識點 → (類別名稱, 類別碼 1–4)。編號順序本就依概念成群，這裡歸併為 4 大類。
CATEGORY = {
    "檔案傳輸": ("檔案傳輸類", 1), "FTP": ("檔案傳輸類", 1), "P2P": ("檔案傳輸類", 1),
    "BBS": ("遠端連線與BBS類", 2), "Telnet": ("遠端連線與BBS類", 2), "遠端登入": ("遠端連線與BBS類", 2),
    "電子郵件": ("電子郵件類", 3), "IMAP": ("電子郵件類", 3), "POP3": ("電子郵件類", 3), "SMTP": ("電子郵件類", 3),
    "即時通訊": ("即時通訊與網路電話類", 4), "IM": ("即時通訊與網路電話類", 4),
    "網路電話": ("即時通訊與網路電話類", 4), "VoIP": ("即時通訊與網路電話類", 4), "Skype": ("即時通訊與網路電話類", 4),
}

# 輸出欄位順序（類別欄放在個別知識點之前，方便一眼看出以類別為單位）
COL_ORDER = [
    "組別", "學生", "學生ID", "題序", "原題序", "時間", "提問",
    "知識點類別碼", "知識點類別", "知識點層級", "知識點",
    "K知識點狀態", "C正確性", "R重複性",
    "是否有效認知", "標註來源",
]


def main() -> None:
    df = pd.read_excel(SRC)

    unknown = sorted(set(df["知識點"]) - set(CATEGORY))
    if unknown:
        raise SystemExit(f"有未歸類的知識點，請補進 CATEGORY：{unknown}")

    df["知識點類別"] = df["知識點"].map(lambda k: CATEGORY[k][0])
    df["知識點類別碼"] = df["知識點"].map(lambda k: CATEGORY[k][1]).astype(int)

    out = df[[c for c in COL_ORDER if c in df.columns]].copy()
    out.to_excel(OUT, index=False)

    print("輸出：", OUT, "| 列數:", len(out), "（與展開版相同，僅加類別欄）")
    print("\n4 大類 × 各組 展開列數：")
    piv = out.pivot_table(index=["知識點類別碼", "知識點類別"], columns="組別",
                          values="題序", aggfunc="count", fill_value=0)
    print(piv.to_string())
    print("\n各類別包含的個別知識點：")
    for code, name in sorted({(v[1], v[0]) for v in CATEGORY.values()}):
        kps = [k for k, v in CATEGORY.items() if v[1] == code]
        print(f"  {code} {name}: {kps}")


if __name__ == "__main__":
    main()
