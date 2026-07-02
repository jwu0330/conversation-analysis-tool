"""序列分析模組單元測試（純函式，不需 Streamlit）。"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sequence import analysis as seq  # noqa: E402


def _df() -> pd.DataFrame:
    # 兩位學生，含不同 Bloom 寫法與亂序，測試排序與解析
    return pd.DataFrame(
        {
            "學生ID": ["S1", "S1", "S1", "S2", "S2", "S2"],
            "組別": ["實驗組", "實驗組", "實驗組", "對照組", "對照組", "對照組"],
            "Bloom層級": ["Level 1", "L2", "Level 4", "L2", "L2", "Level 3"],
            "對話ID": ["D3", "D1", "D2", "D1", "D2", "D3"],  # 故意亂序
        }
    )


def test_parse_bloom_level():
    assert seq.parse_bloom_level("Level 4") == 4
    assert seq.parse_bloom_level("L0") == 0
    assert seq.parse_bloom_level(5) == 5
    assert seq.parse_bloom_level("無") is None
    assert seq.parse_bloom_level(None) is None


def test_guess_columns():
    g = seq.guess_columns(["學生ID", "組別", "Bloom層級", "對話ID"])
    assert g["student"] == "學生ID"
    assert g["group"] == "組別"
    assert g["bloom"] == "Bloom層級"
    assert g["order"] is not None


def test_prepare_and_sequence_order():
    work = seq.prepare(_df(), "學生ID", "組別", "Bloom層級", "對話ID")
    assert len(work) == 6
    seqs = seq.build_sequences(work)
    s1 = seqs[seqs["學生"] == "S1"].iloc[0]["序列"]
    # 依 對話ID 排序 D1->D2->D3 => L2, L4, L1
    assert s1 == [2, 4, 1], s1


def test_transitions():
    work = seq.prepare(_df(), "學生ID", "組別", "Bloom層級", "對話ID")
    t = seq.transitions(work)
    # S1: 2->4, 4->1 ；S2: 2->2, 2->3  → 共 4 條轉移
    assert t["次數"].sum() == 4
    row = t[(t["組別"] == "實驗組") & (t["Source"] == 2) & (t["Target"] == 4)]
    assert int(row["次數"].iloc[0]) == 1


def test_transition_matrix_normalize():
    work = seq.prepare(_df(), "學生ID", "組別", "Bloom層級", "對話ID")
    t = seq.transitions(work)
    levels = seq.all_levels(work)
    mat = seq.transition_matrix(t, "對照組", levels, normalize=True)
    # 對照組 source=L2 有兩條 (->2, ->3)，列機率合計應為 100
    assert abs(mat.loc["L2"].sum() - 100) < 0.01


def test_high_low():
    work = seq.prepare(_df(), "學生ID", "組別", "Bloom層級", "對話ID")
    hl = seq.high_low_transitions(work, high_min=4)
    assert hl["次數"].sum() == 4
    assert set(hl["Source"]).issubset({"高階", "低階"})


def test_position_profile():
    work = seq.prepare(_df(), "學生ID", "組別", "Bloom層級", "對話ID")
    prof = seq.position_profile(work)
    assert set(prof["題序"]) == {1, 2, 3}


def test_exclude_l0():
    df = pd.DataFrame(
        {
            "學生ID": ["S1", "S1", "S1"],
            "組別": ["A", "A", "A"],
            "Bloom層級": ["L0", "L2", "L3"],
            "對話ID": [1, 2, 3],
        }
    )
    work = seq.prepare(df, "學生ID", "組別", "Bloom層級", "對話ID", include_l0=False)
    assert 0 not in work[seq.BLOOM].tolist()


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as err:
                failed += 1
                print(f"FAIL {name}: {err}")
    print("=" * 40)
    print("ALL PASSED" if failed == 0 else f"{failed} test(s) FAILED")
    sys.exit(1 if failed else 0)
