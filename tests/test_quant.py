"""準實驗量化統計測試：以手算值驗證每個統計量與效果量，確保對齊 SPSS。

執行：
    python tests/test_quant.py
    或 python -m pytest -q tests/test_quant.py
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.quant import stats as q  # noqa: E402


def test_independent_t_hand():
    a = [1, 2, 3, 4, 5]
    b = [2, 3, 4, 5, 6]
    r = q.independent_t_test(a, b)
    pooled = r["表"].iloc[0]
    # sp=sqrt(2.5)=1.5811；t = -1/(sp*sqrt(0.4)) = -1.0；df=8
    assert abs(pooled["t"] - (-1.0)) < 1e-9
    assert pooled["df"] == 8
    # Cohen's d = md/sp = -1/1.5811 = -0.6325
    assert abs(r["cohens_d"] - (-1 / math.sqrt(2.5))) < 1e-9
    # 兩組等變異 → Levene p 接近 1
    assert r["Levene_p"] > 0.99


def test_paired_t_hand():
    pre = [1, 2, 3, 4, 5]
    post = [2, 4, 5, 4, 8]
    r = q.paired_t_test(pre, post)
    diff = np.array(post) - np.array(pre)
    assert abs(r["平均差(後-前)"] - diff.mean()) < 1e-9
    assert abs(r["差異SD"] - diff.std(ddof=1)) < 1e-9
    # d_z = mean(diff)/sd(diff)
    assert abs(r["cohens_d"] - diff.mean() / diff.std(ddof=1)) < 1e-9
    assert r["df"] == 4


def test_anova_equals_t_squared():
    # 2 組 ANOVA 的 F 應等於獨立 t 的平方；partial η² = t²/(t²+df)
    df = pd.DataFrame({
        "分數": [1, 2, 3, 4, 5, 2, 3, 4, 5, 6],
        "組別": ["A"] * 5 + ["B"] * 5,
    })
    r = q.one_way_anova(df, "分數", "組別")
    assert abs(r["F"] - 1.0) < 1e-6          # t=-1 → F=1
    assert abs(r["partial_eta2"] - (1 / 9)) < 1e-6   # 1/(1+8)
    assert r["df1"] == 1 and r["df2"] == 8


def test_regression_perfect():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [2, 4, 6, 8, 10]})
    r = q.linear_regression(df, "y", ["x"])
    assert abs(r["R2"] - 1.0) < 1e-9
    coef = r["係數表"].set_index("預測項")
    assert abs(coef.loc["x", "b"] - 2.0) < 1e-9
    assert abs(coef.loc["x", "標準化β"] - 1.0) < 1e-9   # 完美線性 → β=1


def test_ancova_adjusted_means():
    # 含殘差變異（非完全線性），用 statsmodels 預測值獨立驗證調整後平均(EMM)
    import statsmodels.formula.api as smf
    df = pd.DataFrame({
        "grp": ["A"] * 5 + ["B"] * 5,
        "pre": [1, 2, 3, 4, 5, 2, 3, 4, 5, 6],
        "post": [2, 4, 5, 6, 7, 3, 3, 6, 6, 9],
    })
    r = q.ancova(df, dv="post", covar="pre", factor="grp")
    # 獨立方法：無交互作用模型，在總平均共變量處預測 → 即 EMM
    m = smf.ols("post ~ C(grp) + pre", data=df).fit()
    grand = df["pre"].mean()
    exp = {g: float(m.predict(pd.DataFrame({"grp": [g], "pre": [grand]}))[0])
           for g in ["A", "B"]}
    adj = r["調整後平均表"].set_index("grp")["調整後平均"]
    assert abs(adj["A"] - exp["A"]) < 1e-6
    assert abs(adj["B"] - exp["B"]) < 1e-6
    assert 0.0 <= r["斜率同質性_p"] <= 1.0
    assert 0.0 <= r["partial_eta2"] <= 1.0


def test_describe():
    r = q.describe([1, 2, 3, 4, 5])
    assert r["n"] == 5
    assert abs(r["平均"] - 3.0) < 1e-9
    assert abs(r["標準差"] - math.sqrt(2.5)) < 1e-9


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
            except Exception as err:  # noqa: BLE001
                failed += 1
                print(f"ERROR {name}: {type(err).__name__}: {err}")
    print("=" * 40)
    print("ALL PASSED" if failed == 0 else f"{failed} test(s) FAILED")
    sys.exit(1 if failed else 0)
