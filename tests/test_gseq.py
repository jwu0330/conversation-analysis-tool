"""GSEQ 滯後序列分析測試：

1) 用手算值驗證公式（期望次數、轉移機率、調整殘差 z）。
2) 證明「網頁 App 用的計算」與「獨立 CLI 用的計算」完全一致
   —— 兩者都呼叫 src/sequence/analysis.py 的同一批函式。

執行：
    python tests/test_gseq.py
    或 python -m pytest -q
"""
from __future__ import annotations

import math
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import run_sequence_analysis as cli  # noqa: E402
from src.sequence import analysis as seq  # noqa: E402


def _trans_2x2() -> pd.DataFrame:
    # O = [[1,3],[2,4]]，L1/L2
    return pd.DataFrame(
        [
            {"組別": "G", "Source": 1, "Target": 1, "次數": 1},
            {"組別": "G", "Source": 1, "Target": 2, "次數": 3},
            {"組別": "G", "Source": 2, "Target": 1, "次數": 2},
            {"組別": "G", "Source": 2, "Target": 2, "次數": 4},
        ]
    )


def test_gseq_formula_by_hand():
    g = seq.gseq_stats(_trans_2x2(), "G", [1, 2])
    cell = g[(g["Source"] == "L1") & (g["Target"] == "L1")].iloc[0]
    # N=10, R1=4, C1=3 → E=1.2；P=1/4=0.25
    assert cell["觀察次數"] == 1
    assert abs(cell["期望次數"] - 1.2) < 1e-9
    assert abs(cell["轉移機率"] - 0.25) < 1e-9
    # z = (1-1.2)/sqrt(1.2*(1-0.4)*(1-0.3)) = -0.2/sqrt(0.504) ≈ -0.28
    expected_z = (1 - 1.2) / math.sqrt(1.2 * 0.6 * 0.7)
    assert abs(cell["調整殘差z"] - round(expected_z, 2)) < 1e-9


def test_gseq_significance_direction():
    # 造一個明顯偏多的轉移：L1->L2 幾乎必然發生
    trans = pd.DataFrame(
        [
            {"組別": "G", "Source": 1, "Target": 2, "次數": 30},
            {"組別": "G", "Source": 2, "Target": 1, "次數": 30},
            {"組別": "G", "Source": 1, "Target": 1, "次數": 1},
            {"組別": "G", "Source": 2, "Target": 2, "次數": 1},
        ]
    )
    g = seq.gseq_stats(trans, "G", [1, 2])
    up = g[(g["Source"] == "L1") & (g["Target"] == "L2")].iloc[0]
    assert up["調整殘差z"] > 1.96
    assert up["顯著"] == "↑ 顯著偏多"


def test_app_and_cli_are_identical():
    """核心一致性：CLI 的 run() 與 App 直接呼叫 analyze() 給出相同結果。"""
    df = pd.DataFrame(
        {
            "學生ID": ["S1", "S1", "S1", "S1", "S2", "S2", "S2", "S2"],
            "組別": ["實驗組"] * 4 + ["對照組"] * 4,
            "Bloom層級": ["L1", "L2", "L4", "L4", "L2", "L3", "L1", "L2"],
            "對話ID": [1, 2, 3, 4, 1, 2, 3, 4],
        }
    )
    cols = {"student": "學生ID", "group": "組別", "bloom": "Bloom層級", "order": "對話ID"}

    # App 端：直接呼叫共用核心
    app_result = seq.analyze(df, "學生ID", "組別", "Bloom層級", "對話ID",
                             include_l0=True, high_min=4, alpha=0.05)
    # CLI 端：透過 CLI 的 run() 包裝（內部同樣呼叫 analyze）
    cli_result = cli.run(df, cols, high_min=4, alpha=0.05, include_l0=True)

    pd.testing.assert_frame_equal(app_result["transitions"], cli_result["transitions"])
    pd.testing.assert_frame_equal(app_result["gseq"], cli_result["gseq"])
    pd.testing.assert_frame_equal(app_result["sequences"], cli_result["sequences"])
    for g in app_result["groups"]:
        pd.testing.assert_frame_equal(app_result["matrices"][g], cli_result["matrices"][g])


def test_observed_counts_consistent():
    """GSEQ 表的觀察次數總和 == 轉移表次數總和（同一份資料的內部一致性）。"""
    df = pd.DataFrame(
        {
            "學生ID": ["S1"] * 5,
            "組別": ["G"] * 5,
            "Bloom層級": ["L1", "L2", "L2", "L4", "L1"],
            "對話ID": [1, 2, 3, 4, 5],
        }
    )
    r = seq.analyze(df, "學生ID", "組別", "Bloom層級", "對話ID")
    assert r["gseq"]["觀察次數"].sum() == r["transitions"]["次數"].sum()


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
