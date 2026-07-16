"""KCR 規則回歸測試。"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.encode_control_kcr import cap_labels, encode_frame, k_status  # noqa: E402


def _frame(questions):
    columns = [
        "組別", "來源列號", "BotName", "CreateTime", "CommonUserName", "CUserID",
        "UserQuestion", "KnowledgePointStatus", "CorrectnessStatus", "RepetitionStatus",
        "InvolvedKnowledgeLabels",
    ]
    return pd.DataFrame([
        ["對照組", i + 1, "", "", "學生", "id", q, "", "", "", ""]
        for i, q in enumerate(questions)
    ], columns=columns)


def test_k_three_states_and_cap():
    assert k_status([]) == "沒有知識點"
    assert k_status(["FTP"]) == "Single"
    assert k_status(["FTP", "P2P"]) == "Multiple"
    labels = cap_labels("SMTP、POP3、IMAP 與電子郵件", ["電子郵件", "SMTP", "POP3", "IMAP"])
    assert labels == ["IMAP", "POP3", "SMTP"]


def test_repeated_starts_at_third_consecutive_occurrence():
    d = encode_frame(_frame(["FTP 是什麼", "FTP 怎麼用", "FTP 有何限制", "FTP 安全嗎"]))
    assert d["RepetitionStatus"].tolist() == ["New", "New", "Repeated", "Repeated"]


def test_multi_knowledge_overlap_counts_and_break_resets():
    d = encode_frame(_frame([
        "FTP 和 P2P 差異", "P2P 和 BBS 差異", "P2P 是什麼", "hi", "P2P 用途",
        "P2P 原理", "P2P 安全嗎",
    ]))
    assert d["RepetitionStatus"].tolist() == [
        "New", "New", "Repeated", "New", "New", "New", "Repeated",
    ]


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as err:  # noqa: BLE001
                failed += 1
                print(f"FAIL {name}: {type(err).__name__}: {err}")
    print("=" * 40)
    print("ALL PASSED" if failed == 0 else f"{failed} test(s) FAILED")
    raise SystemExit(1 if failed else 0)
