"""核心模組單元測試（純函式，不需啟動 Streamlit）。

執行：
    python -m pytest -q          # 若已安裝 pytest
    python tests/test_core.py    # 直接執行也可（內含簡易 runner）
"""
from __future__ import annotations

import os
import sys
from io import BytesIO

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import (  # noqa: E402
    column_types,
    data_quality,
    descriptive,
    data_loader,
    stat_tests,
)
from src.core import ancova


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


def test_excel_can_list_sheets_then_load_same_upload():
    path = os.path.join(os.path.dirname(__file__), "..", "sample_data", "conversation_sample.xlsx")
    with open(path, "rb") as fh:
        upload = BytesIO(fh.read())
    sheets = data_loader.get_excel_sheets(upload, "sample.xlsx")
    loaded = data_loader.load_any(upload, "sample.xlsx", sheets[0])
    assert sheets == ["Sheet1"]
    assert not loaded.empty


def test_anova_hand_value_and_welch_switch():
    equal = pd.DataFrame({"y": [1, 2, 3, 4, 5, 2, 3, 4, 5, 6, 3, 4, 5, 6, 7],
                          "g": ["A"] * 5 + ["B"] * 5 + ["C"] * 5})
    r = stat_tests.one_way_anova(equal, "y", "g")
    assert r.statistic > 0
    assert r.method.startswith("一因子")
    unequal = pd.DataFrame({"y": [1, 1, 1, 1, 2, 0, 10, 20, 30, 40, 2, 3, 4, 5, 6],
                            "g": ["A"] * 5 + ["B"] * 5 + ["C"] * 5})
    rw = stat_tests.one_way_anova(unequal, "y", "g")
    assert rw.method.startswith("Welch")
    assert rw.extra["採用方法"] == "Welch ANOVA + Games-Howell"


def test_anova_rejects_two_groups_and_routes_to_t_test():
    frame = pd.DataFrame({"y": [1, 2, 3, 2, 3, 4], "g": ["A"] * 3 + ["B"] * 3})
    r = stat_tests.one_way_anova(frame, "y", "g")
    assert np.isnan(r.p_value)
    assert "2 組請用 t 檢定" in r.warnings[0]


def test_friedman_count_uses_repeated_units():
    rows = []
    for student, counts in {"s1": [1, 3, 5], "s2": [2, 4, 6], "s3": [1, 2, 4]}.items():
        for category, count in zip(["A", "B", "C"], counts):
            rows.extend({"學生": student, "類別": category} for _ in range(count))
    r = stat_tests.friedman_count_test(pd.DataFrame(rows), "學生", "類別")
    assert r.method.startswith("Friedman")
    assert r.extra["觀察單位數"] == 3
    assert 0 <= r.effect_size["Kendall's W"] <= 1


def test_ancova_adjusted_means_and_type3_identity():
    frame = pd.DataFrame({
        "grp": ["A"] * 5 + ["B"] * 5,
        "pre": [1, 2, 3, 4, 5, 2, 3, 4, 5, 6],
        "post": [2, 4, 5, 6, 7, 3, 3, 6, 6, 9],
    })
    r = ancova.run_ancova(frame, "post", "grp", ["pre"])
    table = r.ancova_table.set_index("來源")
    assert abs(table.loc["校正後總數", "型III平方和"] -
               table.loc["修正的模型", "型III平方和"] -
               table.loc["錯誤", "型III平方和"]) < 0.002
    assert len(r.adjusted_means) == 2
    assert 0 <= r.group_eta2 <= 1


def test_ancova_multiple_covariates_reports_matching_terms():
    n = 16
    frame = pd.DataFrame({
        "grp": ["A"] * 8 + ["B"] * 8,
        "x1": np.tile(np.arange(1, 9), 2),
        "x2": np.tile(np.arange(8, 0, -1), 2) + np.arange(n) * 0.01,
        "post": np.arange(n) * 0.7 + np.tile([0.2, -0.1], 8),
    })
    r = ancova.run_ancova(frame, "post", "grp", ["x1", "x2"])
    assert len(r.slope_homogeneity) == 2
    for term in r.slope_homogeneity["交乘項（組別×共變量）"]:
        assert term in r.article_en and term in r.article_zh


def test_ancova_levene_uses_model_residuals_like_spss():
    frame = pd.DataFrame({
        "grp": ["A"] * 6 + ["B"] * 6,
        "pre": [1, 2, 3, 4, 5, 6, 2, 3, 4, 5, 6, 9],
        "post": [2, 4, 5, 6, 7, 9, 3, 3, 6, 6, 9, 15],
    })
    r = ancova.run_ancova(frame, "post", "grp", ["pre"])
    # 手算：先以 post ~ grp + pre 取殘差，再對 |殘差| 做單因子 ANOVA
    import statsmodels.formula.api as smf
    from scipy import stats
    resid = smf.ols("post ~ C(grp) + pre", data=frame).fit().resid.abs()
    f, p = stats.f_oneway(resid[frame["grp"] == "A"], resid[frame["grp"] == "B"])
    assert abs(r.levene["F"] - round(f, 3)) < 1e-9
    assert abs(r.levene["p值"] - round(p, 4)) < 1e-9


def test_ancova_slope_report_uses_interaction_model_df():
    frame = pd.DataFrame({
        "grp": ["A"] * 5 + ["B"] * 5,
        "pre": [1, 2, 3, 4, 5, 2, 3, 4, 5, 6],
        "post": [2, 4, 5, 6, 7, 3, 3, 6, 6, 9],
    })
    r = ancova.run_ancova(frame, "post", "grp", ["pre"])
    # n=10、2 組、1 共變量：含交乘項模型誤差 df = 10 - 4 = 6（主模型才是 7）
    assert "F(1, 6)" in r.article_en and "F(1, 6)" in r.article_zh


def test_kendall_uses_asymptotic_p():
    from scipy import stats
    frame = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7], "b": [2, 1, 4, 3, 6, 7, 5]})
    row = descriptive.correlation_pairs(frame, ["a", "b"], method="kendall").iloc[0]
    expected = stats.kendalltau(frame["a"], frame["b"], method="asymptotic").pvalue
    assert row["p值"] == round(float(expected), 4)


def test_describe_counts_use_raw_column_for_categorical():
    out = descriptive.describe_numeric(pd.Series(["甲", "乙", None, "甲"]),
                                       ["count", "missing", "unique"]).set_index("統計量")["數值"]
    assert out["總筆數"] == 3 and out["缺漏值數量"] == 1 and out["不重複值數量"] == 2


def test_t_test_reports_df():
    df = _sample_df()
    r = stat_tests.independent_t_test(df, "分數", "組別")
    assert r.extra["自由度"] == 10.0 or r.extra["採用方法"].startswith("Welch")
    assert "t(" in r.interpretation


def test_frequency_cumulative_not_from_rounded_percent():
    out = descriptive.frequency_table(pd.Series(["a", "b", "c"]))
    assert out["累積百分比(%)"].iloc[-1] == 100.0


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
