"""核心模組單元測試（純函式，不需啟動 Streamlit）。

執行：
    python -m pytest -q          # 若已安裝 pytest
    python tests/test_core.py    # 直接執行也可（內含簡易 runner）
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import (  # noqa: E402
    column_types,
    data_quality,
    descriptive,
    stat_tests,
)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "組別": ["實驗組"] * 6 + ["對照組"] * 6,
            "層級": ["高", "高", "高", "低", "低", "高", "低", "低", "低", "高", "低", "低"],
            "分數": [90, 85, 88, 60, 55, 92, 50, 40, 45, 70, 42, 48],
        }
    )


def test_infer_types():
    df = _sample_df()
    assert column_types.infer_column_type(df["組別"]) == column_types.CATEGORICAL
    assert column_types.infer_column_type(df["分數"]) == column_types.NUMERIC


def test_missing_and_duplicate():
    df = _sample_df()
    assert int(data_quality.missing_report(df)["缺漏數"].sum()) == 0
    assert data_quality.duplicate_report(df)["duplicate_rows"] >= 0


def test_describe_numeric():
    df = _sample_df()
    res = descriptive.describe_numeric(df["分數"], ["count", "mean", "max", "min"])
    values = dict(zip(res["統計量"], res["數值"]))
    assert values["總筆數"] == 12
    assert values["最大值"] == 92
    assert values["最小值"] == 40


def test_frequency_table():
    df = _sample_df()
    freq = descriptive.frequency_table(df["層級"])
    assert freq["次數"].sum() == 12
    assert abs(freq["百分比(%)"].sum() - 100) < 0.01


def test_independent_t_test():
    df = _sample_df()
    result = stat_tests.independent_t_test(df, "分數", "組別")
    assert not np.isnan(result.p_value)
    assert 0 <= result.p_value <= 1
    assert "Cohen's d" in result.effect_size
    assert isinstance(result.interpretation, str) and result.interpretation


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
