# -*- coding: utf-8 -*-
"""由真實對話資料 Bloom_序列分析_精簡.xlsx 產生「知識點涵蓋」兩份資料。

  A. 知識點_原始版_467.xlsx    467 筆、對照組知識點已逐題語意補齊（給 t 檢定/SOLO 等其他分析，統計不重複）
  B. 知識點_序列展開版.xlsx    一題多知識點拆成多筆、每個知識點各算一次、序列重新編序（專給知識點序列分析）

對照組原本知識點欄全空，本腳本用「逐題語意標註」補齊（見 CONTROL_KP）。
實驗組沿用原本已標的知識點。節點欄＝知識點層級(1–15)，序列分析頁會自動抓（欄名含「層級」）。
"""
from __future__ import annotations
import os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "對話分析", "Bloom_序列分析_精簡.xlsx")
OUT_DIR = os.path.join(ROOT, "data", "對話分析")

# 15 知識點 → 編號
KP_NUM = {
    "檔案傳輸": 1, "FTP": 2, "P2P": 3, "BBS": 4, "Telnet": 5, "遠端登入": 6,
    "電子郵件": 7, "IMAP": 8, "POP3": 9, "SMTP": 10, "即時通訊": 11, "IM": 12,
    "網路電話": 13, "VoIP": 14, "Skype": 15,
}

# 對照組逐題語意標註（key＝原始列索引 272–466；空清單＝非 15 知識點之題目，如 自由軟體/URL/TLS）
CONTROL_KP = {
    272: ["P2P", "FTP"], 273: ["Telnet", "遠端登入"], 274: ["遠端登入"], 275: ["BBS"],
    276: ["電子郵件", "SMTP", "POP3", "IMAP"], 277: ["電子郵件", "SMTP", "POP3"],
    278: ["P2P"], 279: ["P2P"], 280: ["BBS"], 281: ["BBS"], 282: ["BBS"],
    283: ["網路電話", "Skype"], 284: ["P2P"], 285: ["P2P"], 286: ["FTP"],
    287: ["Telnet"], 288: ["Telnet"], 289: ["BBS"], 290: ["網路電話"],
    291: ["VoIP", "網路電話"], 292: ["網路電話"], 293: ["IMAP", "電子郵件"],
    294: ["電子郵件"], 295: ["電子郵件"], 296: ["電子郵件"], 297: ["P2P"], 298: ["P2P"],
    299: ["FTP"], 300: ["FTP"], 301: ["電子郵件", "SMTP", "POP3"], 302: ["電子郵件", "SMTP", "POP3"],
    303: ["電子郵件", "SMTP", "POP3"], 304: ["POP3"], 305: ["SMTP"], 306: ["SMTP", "POP3"],
    307: ["SMTP", "POP3"], 308: ["SMTP", "POP3"], 309: ["POP3"], 310: ["SMTP"],
    311: ["電子郵件"], 312: ["電子郵件"], 313: ["電子郵件"], 314: ["電子郵件"], 315: ["電子郵件"],
    316: [], 317: [], 318: [], 319: [],
    320: ["網路電話"], 321: ["網路電話"], 322: ["VoIP"], 323: ["網路電話"], 324: ["網路電話"],
    325: ["網路電話"], 326: ["SMTP", "電子郵件"], 327: ["電子郵件"],
    328: ["電子郵件", "SMTP", "IMAP", "POP3"], 329: ["電子郵件", "SMTP", "POP3"],
    330: ["IMAP", "POP3"], 331: ["SMTP"], 332: ["電子郵件", "SMTP", "POP3"],
    333: ["VoIP", "網路電話"], 334: ["即時通訊", "IM"], 335: ["電子郵件"], 336: ["P2P"],
    337: ["Telnet", "遠端登入"], 338: ["BBS"], 339: ["FTP"], 340: ["FTP"], 341: ["FTP"],
    342: [], 343: ["BBS", "Telnet", "遠端登入"], 344: ["Telnet"], 345: ["BBS"], 346: ["FTP"],
    347: ["即時通訊"], 348: ["即時通訊"], 349: ["即時通訊"], 350: ["POP3", "IMAP", "電子郵件"],
    351: ["P2P"], 352: ["P2P"], 353: ["BBS"], 354: ["BBS"], 355: ["FTP"], 356: ["FTP"],
    357: ["FTP", "檔案傳輸"], 358: ["P2P"], 359: ["P2P"], 360: ["BBS"], 361: ["BBS", "Telnet"],
    362: ["FTP"], 363: ["FTP"], 364: ["FTP"], 365: ["電子郵件", "IMAP", "POP3"], 366: ["P2P"],
    367: ["FTP"], 368: ["FTP", "檔案傳輸"], 369: ["P2P"], 370: ["電子郵件"], 371: ["BBS"],
    372: ["VoIP"], 373: ["SMTP", "POP3", "IMAP", "電子郵件"], 374: ["電子郵件", "SMTP", "POP3", "IMAP"],
    375: ["FTP", "檔案傳輸"], 376: ["FTP"], 377: ["電子郵件"], 378: ["電子郵件"], 379: ["BBS"],
    380: ["FTP"], 381: ["BBS"], 382: ["電子郵件"], 383: ["BBS"], 384: ["FTP"],
    385: ["電子郵件"], 386: ["電子郵件"], 387: ["BBS"], 388: [], 389: [], 390: [],
    391: ["檔案傳輸"], 392: ["檔案傳輸"], 393: ["檔案傳輸"], 394: ["P2P"],
    395: ["IMAP", "SMTP", "POP3", "電子郵件"], 396: ["SMTP", "POP3"], 397: ["P2P"], 398: ["P2P"],
    399: ["P2P"], 400: ["P2P"], 401: ["BBS"], 402: ["BBS"], 403: ["FTP"], 404: ["FTP"],
    405: ["FTP"], 406: ["FTP"], 407: ["FTP"], 408: ["P2P"], 409: ["P2P"], 410: ["P2P"],
    411: ["網路電話"], 412: ["網路電話"], 413: ["FTP"], 414: ["P2P"], 415: ["P2P"],
    416: ["BBS"], 417: ["IMAP"], 418: ["P2P"], 419: ["BBS"], 420: ["IMAP", "POP3"],
    421: ["IMAP"], 422: ["P2P"], 423: ["P2P"], 424: ["P2P"], 425: ["IMAP", "SMTP", "電子郵件"],
    426: ["IMAP"], 427: ["P2P"], 428: ["BBS"], 429: ["FTP"], 430: ["SMTP", "電子郵件"],
    431: ["SMTP"], 432: ["P2P"], 433: ["BBS"], 434: ["FTP"], 435: ["P2P"], 436: ["P2P"],
    437: ["P2P"], 438: ["P2P"], 439: ["P2P"], 440: ["P2P"], 441: ["FTP"], 442: ["VoIP"],
    443: ["FTP"], 444: ["FTP"], 445: ["FTP"], 446: ["FTP"], 447: [], 448: [], 449: [],
    450: ["SMTP", "POP3", "電子郵件"], 451: ["網路電話", "即時通訊"], 452: ["P2P"], 453: ["BBS"],
    454: ["遠端登入"], 455: ["檔案傳輸"], 456: ["FTP"], 457: ["電子郵件"], 458: ["電子郵件"],
    459: ["電子郵件"], 460: ["BBS"], 461: ["FTP"], 462: ["即時通訊"], 463: ["即時通訊", "IM"],
    464: ["網路電話"], 465: ["網路電話", "VoIP"], 466: ["Telnet"],
}


def split_kp(v) -> list[str]:
    if pd.isna(v):
        return []
    return [x.strip() for x in str(v).replace("｜", "|").split("|")
            if x.strip() and x.strip() in KP_NUM]


def main():
    df = pd.read_excel(SRC)
    kp_lists, sources = [], []
    for idx, r in df.iterrows():
        if r["組別"] == "實驗組":
            kps = split_kp(r["知識點"]); src = "實驗組_原標"
        else:
            kps = [k for k in CONTROL_KP.get(idx, []) if k in KP_NUM]; src = "對照組_語意標"
        kp_lists.append(kps); sources.append(src)
    df["_kps"] = kp_lists
    df["標註來源"] = sources

    # ── A. 原始版 467（補齊、不展開）──
    a = df.copy()
    a["知識點"] = a["_kps"].map(lambda ks: " | ".join(ks))
    a["知識點數"] = a["_kps"].map(len)
    a = a.drop(columns=["_kps"])
    a_path = os.path.join(OUT_DIR, "知識點_原始版_467.xlsx")
    a.to_excel(a_path, index=False)

    # ── B. 序列展開版（多知識點拆開、每個各一列、序列重新編序）──
    rows = []
    for (grp, sid), g in df.groupby(["組別", "學生"], sort=False):
        seq_no = 0
        for _, r in g.sort_values("題序").iterrows():
            for kp in r["_kps"]:
                seq_no += 1
                rows.append({
                    "組別": grp, "學生": sid, "學生ID": r["學生ID"],
                    "題序": seq_no, "原題序": r["題序"], "時間": r.get("時間"),
                    "提問": r["提問"], "知識點": kp, "知識點層級": KP_NUM[kp],
                    "是否有效認知": r.get("是否有效認知"), "標註來源": r["標註來源"],
                })  # 不放 Bloom 欄：展開版專供知識點序列，避免搶到節點欄
    b = pd.DataFrame(rows)
    b_path = os.path.join(OUT_DIR, "知識點_序列展開版.xlsx")
    b.to_excel(b_path, index=False)

    # ── 摘要 ──
    print("A 原始版 :", a_path, "| 列數:", len(a))
    print("   對照組已補齊知識點筆數:", (df[df['組別']=='對照組']['_kps'].map(len) > 0).sum(), "/",
          (df['組別']=='對照組').sum())
    print("B 展開版 :", b_path, "| 列數:", len(b), "（原 467 → 展開）")
    for grp, gg in b.groupby("組別"):
        print(f"   {grp}: 展開列 {len(gg)}, 涵蓋知識點 {gg['知識點'].nunique()} 種")
    print("\n各組知識點涵蓋（展開後次數）:")
    piv = b.pivot_table(index="知識點", columns="組別", values="題序", aggfunc="count", fill_value=0)
    print(piv.to_string())


if __name__ == "__main__":
    main()
