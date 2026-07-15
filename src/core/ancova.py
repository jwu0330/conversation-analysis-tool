"""共變數分析 ANCOVA（SPSS 式流程，純函式，不依賴 Streamlit）。

完整流程（對照 SPSS「一般線性模型 → 單變量」）：
    1. 各組描述統計（n、平均、標準差）
    2. 變異數同質性檢定（Levene）—— ANCOVA 前提假設之一
    3. 迴歸斜率同質性檢定（組別 × 共變量交互作用）—— ANCOVA 最關鍵前提
    4. 主分析：型 III 平方和 ANCOVA 表（F、p、淨 η²）
    5. 調整後平均數（EMMeans，把共變量控制在總平均）
    6. 事後比較（調整後平均數的兩兩比較，Bonferroni 校正）

型 III 平方和：statsmodels `anova_lm(model, typ=3)`。
淨 η²(partial eta squared) = SS_effect / (SS_effect + SS_residual)。
調整後平均數以「共變量 = 總平均」代入迴歸模型預測；兩兩差異的檢定用
模型的完整共變異數矩陣（`OLS.t_test`），因此與 SPSS 的 EMMeans 對照一致。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import pandas as pd
import patsy
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.anova import anova_lm


@dataclass
class AncovaResult:
    dv: str
    group: str
    covars: list[str]
    groups: list[str]
    n_total: int
    descriptives: pd.DataFrame          # 各組 n / 平均 / 標準差
    levene: dict                        # 變異數同質性
    slope_homogeneity: pd.DataFrame     # 迴歸斜率同質性（交互作用）
    slope_ok: bool                      # 斜率同質假設是否成立
    ancova_table: pd.DataFrame          # 主 ANCOVA 表（型 III）
    adjusted_means: pd.DataFrame        # 調整後平均數
    posthoc: pd.DataFrame               # 事後兩兩比較
    alpha: float = 0.05
    warnings: list[str] = field(default_factory=list)


def _prep(df: pd.DataFrame, dv: str, group: str, covars: list[str]):
    """轉成安全欄名（Y / G / X1..Xk），去缺漏，回傳 (乾淨資料, x欄清單, 組別對照)。"""
    covars = list(covars)
    cols = [dv, group] + covars
    d = df[cols].copy()
    rename = {dv: "Y", group: "G"}
    for i, c in enumerate(covars):
        rename[c] = f"X{i + 1}"
    d = d.rename(columns=rename)
    d["Y"] = pd.to_numeric(d["Y"], errors="coerce")
    xcols = [f"X{i + 1}" for i in range(len(covars))]
    for x in xcols:
        d[x] = pd.to_numeric(d[x], errors="coerce")
    d = d.dropna(subset=["Y", "G"] + xcols)
    d["G"] = d["G"].astype(str)
    return d, xcols


def run_ancova(
    df: pd.DataFrame,
    dv: str,
    group: str,
    covars: list[str],
    alpha: float = 0.05,
) -> AncovaResult:
    """執行完整 SPSS 式 ANCOVA，回傳所有中間與最終表格。"""
    if not covars:
        raise ValueError("ANCOVA 至少需要一個共變量（covariate）。")
    d, xcols = _prep(df, dv, group, covars)
    groups = sorted(d["G"].unique().tolist())
    if len(groups) < 2:
        raise ValueError(f"組別「{group}」只有 {len(groups)} 組，ANCOVA 需至少 2 組。")
    if len(d) < len(groups) + len(xcols) + 2:
        raise ValueError("有效樣本數過少，不足以估計 ANCOVA 模型。")

    warnings: list[str] = []
    xterms = " + ".join(xcols)

    # --- 1. 描述統計 ---
    desc = (
        d.groupby("G")["Y"]
        .agg(人數="count", 平均="mean", 標準差="std")
        .round(3)
        .reset_index()
        .rename(columns={"G": group})
    )

    # --- 2. Levene 變異數同質性 ---
    samples = [g["Y"].to_numpy(float) for _, g in d.groupby("G")]
    lev_stat, lev_p = stats.levene(*samples, center="mean")
    levene = {
        "統計量W": round(float(lev_stat), 4),
        "p值": round(float(lev_p), 4),
        "同質(p≥α)": bool(lev_p >= alpha),
    }
    if lev_p < alpha:
        warnings.append(
            f"Levene p = {lev_p:.4f} < {alpha}：各組變異數不同質，ANCOVA 結果需謹慎解讀。"
        )

    # --- 3. 迴歸斜率同質性（組別 × 共變量交互作用）---
    inter_terms = " + ".join([f"C(G):{x}" for x in xcols])
    model_full = smf.ols(f"Y ~ C(G) + {xterms} + {inter_terms}", data=d).fit()
    aov_full = anova_lm(model_full, typ=3)
    inter_rows = [ix for ix in aov_full.index if ":" in ix]
    slope_tbl = (
        aov_full.loc[inter_rows, ["F", "PR(>F)"]]
        .rename(columns={"PR(>F)": "p值"})
        .round(4)
        .reset_index()
        .rename(columns={"index": "交互作用項"})
    )
    slope_min_p = float(aov_full.loc[inter_rows, "PR(>F)"].min()) if inter_rows else 1.0
    slope_ok = slope_min_p >= alpha
    if not slope_ok:
        warnings.append(
            f"迴歸斜率同質性檢定 p = {slope_min_p:.4f} < {alpha}：組別與共變量有交互作用，"
            "違反 ANCOVA 前提，宜改用其他方法（如 Johnson-Neyman 或分組迴歸）。"
        )

    # --- 4. 主 ANCOVA（型 III，共同斜率模型）---
    model = smf.ols(f"Y ~ C(G) + {xterms}", data=d).fit()
    aov = anova_lm(model, typ=3)
    ss_res = float(aov.loc["Residual", "sum_sq"])

    def _label(idx: str) -> str:
        if idx == "C(G)":
            return f"組別（{group}）"
        if idx == "Intercept":
            return "截距"
        if idx == "Residual":
            return "誤差"
        for i, c in enumerate(covars):
            if idx == f"X{i + 1}":
                return f"共變量（{c}）"
        return idx

    rows = []
    for idx in aov.index:
        ss = float(aov.loc[idx, "sum_sq"])
        dfree = float(aov.loc[idx, "df"])
        f_val = aov.loc[idx, "F"]
        p_val = aov.loc[idx, "PR(>F)"]
        peta = ss / (ss + ss_res) if idx != "Residual" and (ss + ss_res) > 0 else None
        rows.append({
            "來源": _label(idx),
            "型III平方和": round(ss, 3),
            "自由度": int(dfree),
            "F": round(float(f_val), 4) if pd.notna(f_val) else None,
            "p值": round(float(p_val), 4) if pd.notna(p_val) else None,
            "淨η²": round(float(peta), 3) if peta is not None else None,
            "顯著": "是" if (pd.notna(p_val) and p_val < alpha) else ("否" if pd.notna(p_val) else "-"),
        })
    ancova_table = pd.DataFrame(rows)

    # --- 5. 調整後平均數（共變量 = 總平均）---
    x_means = {x: float(d[x].mean()) for x in xcols}
    newd = pd.DataFrame({"G": groups})
    for x in xcols:
        newd[x] = x_means[x]
    pred = model.get_prediction(newd).summary_frame(alpha=alpha)
    adj = pd.DataFrame({
        group: groups,
        "調整後平均": pred["mean"].round(3).to_numpy(),
        "標準誤": pred["mean_se"].round(3).to_numpy(),
        f"{int((1 - alpha) * 100)}%CI下限": pred["mean_ci_lower"].round(3).to_numpy(),
        f"{int((1 - alpha) * 100)}%CI上限": pred["mean_ci_upper"].round(3).to_numpy(),
    })
    cov_note = "、".join(f"{c}={x_means[f'X{i + 1}']:.3f}" for i, c in enumerate(covars))
    adj.attrs["說明"] = f"共變量固定於總平均（{cov_note}）"

    # --- 6. 事後兩兩比較（調整後平均數差異，Bonferroni）---
    design = model.model.data.design_info
    exog_g = np.asarray(patsy.build_design_matrices([design], newd)[0])
    idx_of = {g: i for i, g in enumerate(groups)}
    pairs = list(combinations(groups, 2))
    n_pairs = max(len(pairs), 1)
    ph_rows = []
    for a, b in pairs:
        contrast = exog_g[idx_of[a]] - exog_g[idx_of[b]]
        tt = model.t_test(contrast)
        p_raw = float(np.ravel(tt.pvalue)[0])
        p_adj = min(p_raw * n_pairs, 1.0)
        ph_rows.append({
            "組別A": a,
            "組別B": b,
            "調整後均差(A−B)": round(float(np.ravel(tt.effect)[0]), 3),
            "標準誤": round(float(np.ravel(tt.sd)[0]), 3),
            "t": round(float(np.ravel(tt.tvalue)[0]), 3),
            "p值(未校正)": round(p_raw, 4),
            "p值(Bonferroni)": round(p_adj, 4),
            "顯著": "是" if p_adj < alpha else "否",
        })
    posthoc = pd.DataFrame(ph_rows)

    return AncovaResult(
        dv=dv, group=group, covars=list(covars), groups=groups, n_total=int(len(d)),
        descriptives=desc, levene=levene, slope_homogeneity=slope_tbl, slope_ok=slope_ok,
        ancova_table=ancova_table, adjusted_means=adj, posthoc=posthoc,
        alpha=alpha, warnings=warnings,
    )
