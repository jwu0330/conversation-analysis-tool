"""對齊 SPSS 的準實驗量化統計（純函式）。

設計原則：效果量與變異數同質性等「Python 預設 ≠ SPSS 預設」之處，
一律以明確公式手動計算，確保與 SPSS 逐位對齊。公式說明見 docs/準實驗分析方法.md。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pingouin as pg
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats


# ---------- 共用工具 ----------
def _arr(x) -> np.ndarray:
    return pd.Series(x, dtype=float).dropna().to_numpy()


def _clean_paired(pre, post) -> tuple[np.ndarray, np.ndarray]:
    """成對資料：只保留兩者皆非缺值的列（pairwise deletion）。"""
    d = pd.DataFrame({"pre": pd.Series(pre, dtype=float),
                      "post": pd.Series(post, dtype=float)}).dropna()
    return d["pre"].to_numpy(), d["post"].to_numpy()


def d_magnitude(d: float) -> str:
    a = abs(d)
    return "小" if a < 0.5 else "中" if a < 0.8 else "大" if a >= 0.8 else "-"


def eta2_magnitude(e: float) -> str:
    return "小" if e < 0.06 else "中" if e < 0.14 else "大"


# ---------- 描述統計 ----------
def describe(x) -> dict:
    """單一變項描述統計。偏態/峰度用 pandas（Fisher、偏誤校正 = SPSS 定義）。"""
    s = pd.Series(x, dtype=float).dropna()
    n = int(s.size)
    sd = float(s.std(ddof=1)) if n > 1 else float("nan")
    return {
        "n": n,
        "平均": float(s.mean()) if n else float("nan"),
        "標準差": sd,
        "標準誤": sd / np.sqrt(n) if n > 1 else float("nan"),
        "最小值": float(s.min()) if n else float("nan"),
        "最大值": float(s.max()) if n else float("nan"),
        "偏態": float(s.skew()) if n > 2 else float("nan"),
        "峰度": float(s.kurt()) if n > 3 else float("nan"),
    }


def describe_by_group(df: pd.DataFrame, dv: str, group: str) -> pd.DataFrame:
    rows = []
    for g, sub in df.groupby(group):
        rows.append({group: g, "變項": dv, **describe(sub[dv])})
    return pd.DataFrame(rows)


# ---------- 效果量（明確公式，對齊 SPSS）----------
def cohens_d_independent(a, b) -> float:
    """獨立樣本 Cohen's d：分母為 pooled SD（SPSS 作法）。"""
    a, b = _arr(a), _arr(b)
    n1, n2 = len(a), len(b)
    s1, s2 = a.std(ddof=1), b.std(ddof=1)
    sp = np.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
    return float((a.mean() - b.mean()) / sp)


def hedges_g_independent(a, b) -> float:
    """Hedges' g：Cohen's d 乘上小樣本校正 J。"""
    a, b = _arr(a), _arr(b)
    df = len(a) + len(b) - 2
    j = 1 - 3 / (4 * df - 1)
    return float(cohens_d_independent(a, b) * j)


def _welch_df(a: np.ndarray, b: np.ndarray) -> float:
    n1, n2 = len(a), len(b)
    v1, v2 = a.var(ddof=1) / n1, b.var(ddof=1) / n2
    return (v1 + v2) ** 2 / (v1**2 / (n1 - 1) + v2**2 / (n2 - 1))


# ---------- 獨立樣本 t 檢定 ----------
def independent_t_test(a, b, alpha: float = 0.05) -> dict:
    """SPSS 風格：Levene(以平均為中心) + 等變異(pooled) 與 不等變異(Welch) 兩列。"""
    a, b = _arr(a), _arr(b)
    n1, n2 = len(a), len(b)
    m1, m2 = a.mean(), b.mean()
    md = m1 - m2

    lev_w, lev_p = stats.levene(a, b, center="mean")

    # 等變異假設（Student pooled）
    t_p, p_p = stats.ttest_ind(a, b, equal_var=True)
    df_p = n1 + n2 - 2
    sp = np.sqrt(((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / df_p)
    se_p = sp * np.sqrt(1 / n1 + 1 / n2)
    tcrit_p = stats.t.ppf(1 - alpha / 2, df_p)
    ci_p = (md - tcrit_p * se_p, md + tcrit_p * se_p)

    # 不等變異（Welch）
    t_w, p_w = stats.ttest_ind(a, b, equal_var=False)
    df_w = _welch_df(a, b)
    se_w = np.sqrt(a.var(ddof=1) / n1 + b.var(ddof=1) / n2)
    tcrit_w = stats.t.ppf(1 - alpha / 2, df_w)
    ci_w = (md - tcrit_w * se_w, md + tcrit_w * se_w)

    d = cohens_d_independent(a, b)
    table = pd.DataFrame([
        {"變異數假設": "假設等變異", "t": t_p, "df": df_p, "雙尾p": p_p,
         "平均差": md, "標準誤差": se_p, "95%CI下": ci_p[0], "95%CI上": ci_p[1]},
        {"變異數假設": "不假設等變異", "t": t_w, "df": df_w, "雙尾p": p_w,
         "平均差": md, "標準誤差": se_w, "95%CI下": ci_w[0], "95%CI上": ci_w[1]},
    ])
    use = "假設等變異" if lev_p >= alpha else "不假設等變異"
    return {
        "n1": n1, "n2": n2, "平均1": m1, "平均2": m2,
        "Levene_W": float(lev_w), "Levene_p": float(lev_p),
        "建議看的列": use,
        "cohens_d": d, "d強度": d_magnitude(d),
        "hedges_g": hedges_g_independent(a, b),
        "表": table,
    }


# ---------- 成對樣本 t 檢定 ----------
def paired_t_test(pre, post, alpha: float = 0.05) -> dict:
    """前後測相依樣本。Cohen's d_z 分母為差異分數 SD（SPSS 作法）。"""
    pre, post = _clean_paired(pre, post)
    diff = post - pre
    n = len(diff)
    md = diff.mean()
    sd_diff = diff.std(ddof=1)
    se = sd_diff / np.sqrt(n)
    t, p = stats.ttest_rel(post, pre)
    df = n - 1
    tcrit = stats.t.ppf(1 - alpha / 2, df)
    ci = (md - tcrit * se, md + tcrit * se)
    d_z = md / sd_diff
    return {
        "n": n, "前測平均": float(pre.mean()), "後測平均": float(post.mean()),
        "平均差(後-前)": float(md), "差異SD": float(sd_diff), "標準誤差": float(se),
        "t": float(t), "df": df, "雙尾p": float(p),
        "95%CI下": float(ci[0]), "95%CI上": float(ci[1]),
        "cohens_d": float(d_z), "d強度": d_magnitude(d_z),
    }


# ---------- 單因子 ANOVA ----------
def one_way_anova(df: pd.DataFrame, dv: str, factor: str, alpha: float = 0.05) -> dict:
    data = df[[dv, factor]].dropna()
    aov = pg.anova(data=data, dv=dv, between=factor, detailed=True)
    row = aov[aov["Source"] == factor].iloc[0]
    resid = aov[aov["Source"] != factor].iloc[-1]  # 殘差/組內列
    np2 = float(row["np2"])
    groups = [sub[dv].to_numpy() for _, sub in data.groupby(factor)]
    lev_w, lev_p = stats.levene(*groups, center="mean")
    welch = pg.welch_anova(data=data, dv=dv, between=factor)
    tukey = pg.pairwise_tukey(data=data, dv=dv, between=factor)
    return {
        "F": float(row["F"]), "df1": int(row["DF"]),
        "df2": int(resid["DF"]),
        "p": float(row["p_unc"]),
        "partial_eta2": np2, "效果量強度": eta2_magnitude(np2),
        "Levene_W": float(lev_w), "Levene_p": float(lev_p),
        "welch": welch, "posthoc_tukey": tukey, "anova表": aov,
    }


# ---------- ANCOVA（共變數分析，Type III）----------
def ancova(df: pd.DataFrame, dv: str, covar: str, factor: str,
           alpha: float = 0.05) -> dict:
    data = df[[dv, covar, factor]].dropna().copy()
    anc = pg.ancova(data=data, dv=dv, covar=covar, between=factor)
    row = anc[anc["Source"] == factor].iloc[0]
    np2 = float(row["np2"])
    p_group = float(row["p_unc"])

    # 迴歸斜率同質性：組別×共變量交互作用是否顯著（不顯著才適用 ANCOVA）
    m_int = smf.ols(f"Q('{dv}') ~ C(Q('{factor}')) * Q('{covar}')", data=data).fit()
    aov_int = sm.stats.anova_lm(m_int, typ=3)
    inter_key = [k for k in aov_int.index if ":" in k][0]
    slope_p = float(aov_int.loc[inter_key, "PR(>F)"])

    # 調整後平均數（EMM）：以共同組內迴歸斜率調整到總平均共變量
    m = smf.ols(f"Q('{dv}') ~ C(Q('{factor}')) + Q('{covar}')", data=data).fit()
    b = float(m.params[f"Q('{covar}')"])
    grand = data[covar].mean()
    adj = []
    for g, sub in data.groupby(factor):
        adj_mean = sub[dv].mean() + b * (grand - sub[covar].mean())
        adj.append({factor: g, "原始平均": float(sub[dv].mean()),
                    "調整後平均": float(adj_mean), "n": int(len(sub))})
    return {
        "F": float(row["F"]), "df": int(row["DF"]), "p": p_group,
        "partial_eta2": np2, "效果量強度": eta2_magnitude(np2),
        "共變量斜率b": b, "斜率同質性_p": slope_p,
        "斜率同質性符合": slope_p >= alpha,
        "調整後平均表": pd.DataFrame(adj), "ancova表": anc,
    }


# ---------- 線性迴歸 ----------
def linear_regression(df: pd.DataFrame, dv: str, predictors: list[str]) -> dict:
    data = df[[dv] + predictors].dropna()
    x = sm.add_constant(data[predictors])
    y = data[dv]
    m = sm.OLS(y, x).fit()
    sd_y = y.std(ddof=1)
    rows = []
    for name in x.columns:
        b = float(m.params[name])
        beta = 0.0 if name == "const" else b * data[name].std(ddof=1) / sd_y
        rows.append({"預測項": name, "b": b, "標準化β": float(beta),
                     "標準誤": float(m.bse[name]), "t": float(m.tvalues[name]),
                     "p": float(m.pvalues[name])})
    return {
        "R2": float(m.rsquared), "調整後R2": float(m.rsquared_adj),
        "F": float(m.fvalue), "模型p": float(m.f_pvalue),
        "df_model": int(m.df_model), "df_resid": int(m.df_resid),
        "係數表": pd.DataFrame(rows),
    }
