from __future__ import annotations

import pandas as pd

from src.core import kcr_metrics


def test_student_metrics_encodes_and_aggregates_per_student():
    frame = pd.DataFrame({
        "學生ID": ["S1", "S1", "S2", "S2"],
        "組別": ["實驗組", "實驗組", "對照組", "對照組"],
        "K知識點狀態": ["沒有知識點", "Multiple", "Single", "Single"],
        "知識點數": [0, 3, 1, 1],
        "C正確性": ["Correct", "Incorrect", "Correct", "Correct"],
        "R重複性": ["New", "Repeated", "New", "New"],
    })

    result = kcr_metrics.student_metrics(frame).set_index("學生")

    assert len(result) == 2
    assert result.loc["S1", "K"] == 1.0
    assert result.loc["S1", "C"] == 0.5
    assert result.loc["S1", "R"] == 0.5
    assert result.loc["S2", "K"] == 1.0


def test_student_metrics_uses_count_when_k_label_is_missing():
    frame = pd.DataFrame({
        "學生": ["S1", "S1"], "組別": ["A", "A"],
        "K知識點狀態": [None, None], "知識點數": [0, 3],
        "C正確性": ["Correct", "Correct"], "R重複性": ["New", "New"],
    })

    result = kcr_metrics.student_metrics(frame)
    assert result.loc[0, "K"] == 1.0
