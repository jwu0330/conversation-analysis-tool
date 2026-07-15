"""共變數分析 ANCOVA —— 完全對齊臺師大吳書豪《量化統計方法實作》SPSS 講義。

流程與必報項目（重要區，依講義順序）：
    1. 各組描述統計         N、平均數(Mean)、標準差(SD)
    2. 常態性檢定           Shapiro-Wilk (n<50) 或 Kolmogorov-Smirnov/Lilliefors (n>=50)
    3. 變異數同質性檢定     Levene（F, df1, df2, p）── 講義以平均為中心
    4. 組內迴歸係數同質性   組別 × 前測(共變量) 交乘項；交乘項放最後；型 I/III
    5. 主分析 ANCOVA        完全因子設計、型 III 平方和；主旨間效果檢定完整表 + 局部 η² + R²
    6. 調整後平均數(EMMeans) 共變量固定於總平均：調整後平均、標準誤、95% CI
    7. APA 彙整表           Group | N | Mean | SD | Adjusted Mean | Adjusted SD(=SE) | F | η²
    8. 假設違反處理建議     常態→無母數U；變異數不同質→前後測t；斜率不同質→詹森內曼

效果量 η² 判準（Cohen, 1988，講義 p23）：.01≤小<.059≤中<.138≤大。
型 III 平方和以 statsmodels anova_lm(typ=3)（sum-to-zero 對比）計算，對齊 SPSS/SAS。
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

try:
    from statsmodels.stats.diagnostic import lilliefors
except Exception:  # pragma: no cover
    lilliefors = None


@dataclass
class AncovaResult:
    dv: str
    group: str
    covars: list[str]
    groups: list[str]
    n_total: int
    descriptives: pd.DataFrame          # 組別 / N / 平均數 / 標準差
    normality: pd.DataFrame             # 各組常態性檢定
    normality_ok: bool
    levene: dict                        # 變異數同質性 F/df1/df2/p
    slope_homogeneity: pd.DataFrame     # 交乘項（組別×共變量）
    slope_ok: bool
    ancova_table: pd.DataFrame          # 主旨間效果檢定（型 III 完整表）
    r_squared: float
    r_squared_adj: float
    adjusted_means: pd.DataFrame        # EMMeans：調整後平均/標準誤/95%CI
    summary_apa: pd.DataFrame           # APA 彙整表
    group_F: float
    group_p: float
    group_eta2: float
    eta2_magnitude: str
    posthoc: pd.DataFrame               # 事後兩兩比較（LSD，補充）
    article_zh: str                     # 文章寫法（中）
    article_en: str                     # 文章寫法（英）
    decisions: list[str]                # 假設違反處理建議
    alpha: float = 0.05
    warnings: list[str] = field(default_factory=list)


def eta2_magnitude(e: float) -> str:
    """η² 效果量強度（Cohen, 1988，講義 p23）。"""
    if e != e:
        return "無法判定"
    if e < 0.01:
        return "極小"
    if e < 0.059:
        return "小效果"
    if e < 0.138:
        return "中效果"
    return "大效果"


def _p_apa(p: float, sig: bool = True) -> str:
    """APA 風格 p 值敘述：達顯著寫 p < .05／.01／.001，未達寫 p > .05。"""
    if p != p:
        return "p = NA"
    if p < 0.05:
        if p < 0.001:
            return "p < .001"
        if p < 0.01:
            return "p < .01"
        return "p < .05"
    return "p > .05"


def _prep(df: pd.DataFrame, dv: str, group: str, covars: list[str]):
    """轉安全欄名（Y / G / X1..Xk），去缺漏；回傳 (乾淨資料, x欄清單)。"""
    covars = list(covars)
    d = df[[dv, group] + covars].copy()
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


def _normality(d: pd.DataFrame, group: str, alpha: float) -> tuple[pd.DataFrame, bool]:
    """各組依變數常態性檢定：n<50 Shapiro-Wilk，n>=50 Kolmogorov-Smirnov(Lilliefors)。"""
    rows: list[dict] = []
    ok = True
    for g, sub in d.groupby("G"):
        y = sub["Y"].to_numpy(float)
        n = len(y)
        if n < 3:
            rows.append({group: g, "檢定": "-", "統計量": None, "p值": None,
                         "n": n, "常態(p≥α)": "-"})
            continue
        if n < 50:
            stat_v, p = stats.shapiro(y)
            name = "Shapiro-Wilk"
        elif lilliefors is not None:
            stat_v, p = lilliefors(y, dist="norm")
            name = "Kolmogorov-Smirnov"
        else:  # pragma: no cover
            stat_v, p = stats.kstest((y - y.mean()) / y.std(ddof=1), "norm")
            name = "Kolmogorov-Smirnov"
        passed = p >= alpha
        ok = ok and passed
        rows.append({group: g, "檢定": name, "統計量": round(float(stat_v), 3),
                     "p值": round(float(p), 4), "n": n,
                     "常態(p≥α)": "是" if passed else "否"})
    return pd.DataFrame(rows), ok


def run_ancova(
    df: pd.DataFrame,
    dv: str,
    group: str,
    covars: list[str],
    alpha: float = 0.05,
) -> AncovaResult:
    """執行完整 SPSS 式 ANCOVA（對齊講義），回傳所有中間與最終表格。"""
    if not covars:
        raise ValueError("ANCOVA 至少需要一個共變量（前測）。")
    d, xcols = _prep(df, dv, group, covars)
    groups = sorted(d["G"].unique().tolist())
    if len(groups) < 2:
        raise ValueError(f"組別「{group}」只有 {len(groups)} 組，ANCOVA 需至少 2 組。")
    if len(d) < len(groups) + len(xcols) + 2:
        raise ValueError("有效樣本數過少，不足以估計 ANCOVA 模型。")

    warnings: list[str] = []
    decisions: list[str] = []
    n_total = int(len(d))
    k = len(groups)
    xterms = " + ".join(xcols)

    # === 1. 描述統計 ===
    desc = (
        d.groupby("G")["Y"]
        .agg(N="count", 平均數="mean", 標準差="std")
        .round(3).reset_index().rename(columns={"G": group})
    )

    # === 2. 常態性檢定 ===
    normality, normality_ok = _normality(d, group, alpha)
    if not normality_ok:
        warnings.append("至少一組未通過常態性檢定（p < α）。")
        decisions.append("【常態性不滿足】改用無母數檢定（Mann-Whitney U，對應獨立樣本 t 檢定）。")

    # === 3. Levene 變異數同質性（以平均為中心）===
    samples = [g["Y"].to_numpy(float) for _, g in d.groupby("G")]
    lev_stat, lev_p = stats.levene(*samples, center="mean")
    levene = {
        "F": round(float(lev_stat), 3), "df1": k - 1, "df2": n_total - k,
        "p值": round(float(lev_p), 4), "同質(p≥α)": bool(lev_p >= alpha),
    }
    if lev_p < alpha:
        warnings.append(f"Levene F = {lev_stat:.3f}, p = {lev_p:.4f} < {alpha}：變異數不同質。")
        decisions.append("【變異數不同質】依講義：前後測都改跑 t 檢定處理。")

    # === 4. 組內迴歸係數同質性（交乘項放最後；型 III）===
    inter_terms = " + ".join([f"C(G, Sum):{x}" for x in xcols])
    model_int = smf.ols(f"Y ~ C(G, Sum) + {xterms} + {inter_terms}", data=d).fit()
    aov_int = anova_lm(model_int, typ=3)
    inter_rows = [ix for ix in aov_int.index if ":" in ix]
    slope_tbl = (
        aov_int.loc[inter_rows, ["F", "PR(>F)"]]
        .rename(columns={"PR(>F)": "p值"}).round(4).reset_index()
        .rename(columns={"index": "交乘項（組別×共變量）"})
    )
    slope_min_p = float(aov_int.loc[inter_rows, "PR(>F)"].min()) if inter_rows else 1.0
    slope_ok = slope_min_p >= alpha
    if not slope_ok:
        warnings.append(f"迴歸斜率同質性 p = {slope_min_p:.4f} < {alpha}：組內迴歸係數不同質。")
        decisions.append("【斜率不同質】依講義：改用詹森-內曼法（Johnson-Neyman）找顯著區間。")

    # === 5. 主分析 ANCOVA（完全因子設計、型 III）===
    model = smf.ols(f"Y ~ C(G, Sum) + {xterms}", data=d).fit()
    aov = anova_lm(model, typ=3)
    ss_resid = float(aov.loc["Residual", "sum_sq"])
    df_resid = float(aov.loc["Residual", "df"])
    ms_resid = ss_resid / df_resid

    y = d["Y"].to_numpy(float)
    ss_total_uncorr = float((y ** 2).sum())            # 總計（未校正）
    ss_corr_total = float(((y - y.mean()) ** 2).sum())  # 校正後總數
    ss_model = ss_corr_total - ss_resid                 # 修正的模型
    df_model = float(sum(aov.loc[t, "df"] for t in aov.index
                         if t not in ("Intercept", "Residual")))
    ms_model = ss_model / df_model if df_model > 0 else float("nan")
    f_model = ms_model / ms_resid if ms_resid > 0 else float("nan")
    p_model = float(stats.f.sf(f_model, df_model, df_resid)) if f_model == f_model else float("nan")
    r2 = ss_model / ss_corr_total if ss_corr_total > 0 else float("nan")
    r2_adj = 1 - (ms_resid / (ss_corr_total / (n_total - 1))) if ss_corr_total > 0 else float("nan")

    def _peta(ss: float) -> float:
        return ss / (ss + ss_resid) if (ss + ss_resid) > 0 else float("nan")

    def _cov_label(idx: str) -> str:
        for i, c in enumerate(covars):
            if idx == f"X{i + 1}":
                return f"共變量（{c}）"
        return idx

    ss_int = float(aov.loc["Intercept", "sum_sq"])
    f_int = float(aov.loc["Intercept", "F"])
    p_int = float(aov.loc["Intercept", "PR(>F)"])
    ss_grp = float(aov.loc["C(G, Sum)", "sum_sq"])
    df_grp = int(aov.loc["C(G, Sum)", "df"])
    f_grp = float(aov.loc["C(G, Sum)", "F"])
    p_grp = float(aov.loc["C(G, Sum)", "PR(>F)"])
    grp_eta2 = _peta(ss_grp)

    rows = [
        {"來源": "修正的模型", "型III平方和": round(ss_model, 3), "自由度": int(df_model),
         "平均值平方": round(ms_model, 3), "F": round(f_model, 3),
         "顯著性": round(p_model, 4), "局部η²": round(_peta(ss_model), 3)},
        {"來源": "截距", "型III平方和": round(ss_int, 3), "自由度": 1,
         "平均值平方": round(ss_int, 3), "F": round(f_int, 3),
         "顯著性": round(p_int, 4), "局部η²": round(_peta(ss_int), 3)},
    ]
    for x in xcols:
        ss = float(aov.loc[x, "sum_sq"])
        rows.append({"來源": _cov_label(x), "型III平方和": round(ss, 3), "自由度": 1,
                     "平均值平方": round(ss, 3), "F": round(float(aov.loc[x, "F"]), 3),
                     "顯著性": round(float(aov.loc[x, "PR(>F)"]), 4),
                     "局部η²": round(_peta(ss), 3)})
    rows.append({"來源": f"組別（{group}）", "型III平方和": round(ss_grp, 3), "自由度": df_grp,
                 "平均值平方": round(ss_grp / df_grp, 3), "F": round(f_grp, 3),
                 "顯著性": round(p_grp, 4), "局部η²": round(grp_eta2, 3)})
    rows.append({"來源": "錯誤", "型III平方和": round(ss_resid, 3), "自由度": int(df_resid),
                 "平均值平方": round(ms_resid, 3), "F": None, "顯著性": None, "局部η²": None})
    rows.append({"來源": "總計", "型III平方和": round(ss_total_uncorr, 3), "自由度": n_total,
                 "平均值平方": None, "F": None, "顯著性": None, "局部η²": None})
    rows.append({"來源": "校正後總數", "型III平方和": round(ss_corr_total, 3), "自由度": n_total - 1,
                 "平均值平方": None, "F": None, "顯著性": None, "局部η²": None})
    ancova_table = pd.DataFrame(rows)

    # === 6. 調整後平均數（EMMeans；共變量固定於總平均）===
    x_means = {x: float(d[x].mean()) for x in xcols}
    newd = pd.DataFrame({"G": groups})
    for x in xcols:
        newd[x] = x_means[x]
    pred = model.get_prediction(newd).summary_frame(alpha=alpha)
    lvl = int((1 - alpha) * 100)
    adj = pd.DataFrame({
        group: groups,
        "調整後平均數": pred["mean"].round(3).to_numpy(),
        "標準誤": pred["mean_se"].round(3).to_numpy(),
        f"{lvl}%CI下限": pred["mean_ci_lower"].round(3).to_numpy(),
        f"{lvl}%CI上限": pred["mean_ci_upper"].round(3).to_numpy(),
    })
    cov_note = "、".join(f"{c}={x_means[f'X{i + 1}']:.3f}" for i, c in enumerate(covars))
    adj.attrs["說明"] = f"共變量固定於總平均（{cov_note}）"

    # === 7. APA 彙整表（Group | N | Mean | SD | Adjusted Mean | Adjusted SD | F | η²）===
    mag = eta2_magnitude(grp_eta2)
    apa_rows = []
    for i, g in enumerate(groups):
        drow = desc[desc[group] == g].iloc[0]
        arow = adj[adj[group] == g].iloc[0]
        apa_rows.append({
            "Group": f"{i + 1}.{g}",
            "N": int(drow["N"]),
            "Mean": round(float(drow["平均數"]), 2),
            "SD": round(float(drow["標準差"]), 2),
            "Adjusted Mean": round(float(arow["調整後平均數"]), 2),
            "Adjusted SD": round(float(arow["標準誤"]), 2),  # 依講義：此欄填調整後標準誤(SE)
            "F": round(f_grp, 2) if i == 0 else None,
            "η²": round(grp_eta2, 3) if i == 0 else None,
            "顯著": ("*" if (i == 0 and p_grp < alpha) else "") if i == 0 else "",
        })
    summary_apa = pd.DataFrame(apa_rows)

    # === 事後兩兩比較（LSD，無校正；講義 選項的信賴區間調整＝LSD）===
    design = model.model.data.design_info
    exog_g = np.asarray(patsy.build_design_matrices([design], newd)[0])
    idx_of = {g: i for i, g in enumerate(groups)}
    ph_rows = []
    for a, b in combinations(groups, 2):
        contrast = exog_g[idx_of[a]] - exog_g[idx_of[b]]
        tt = model.t_test(contrast)
        p_raw = float(np.ravel(tt.pvalue)[0])
        ph_rows.append({
            "組別A": a, "組別B": b,
            "調整後均差(A−B)": round(float(np.ravel(tt.effect)[0]), 3),
            "標準誤": round(float(np.ravel(tt.sd)[0]), 3),
            "t": round(float(np.ravel(tt.tvalue)[0]), 3),
            "p值(LSD)": round(p_raw, 4),
            "顯著": "是" if p_raw < alpha else "否",
        })
    posthoc = pd.DataFrame(ph_rows)

    # === 文章寫法（中/英，套講義模板）===
    lev_txt_en = _p_apa(lev_p)
    slope_txt_en = _p_apa(slope_min_p)
    grp_txt_en = _p_apa(p_grp)
    adj_map = {g: adj[adj[group] == g].iloc[0] for g in groups}
    parts_en = ", ".join(
        f"{round(float(adj_map[g]['調整後平均數']),2)} and "
        f"{round(float(adj_map[g]['標準誤']),2)} for the {g}"
        for g in groups
    )
    article_en = (
        f"The Levene's test of determining homogeneity of variance was "
        f"{'not violated' if levene['同質(p≥α)'] else 'violated'} (F = {levene['F']}, {lev_txt_en}). "
        f"In addition, the homogeneity of regression slopes was "
        f"{'confirmed' if slope_ok else 'NOT confirmed'} (F = {slope_tbl['F'].iloc[0] if not slope_tbl.empty else float('nan')}, {slope_txt_en}), "
        f"indicating that it was {'appropriate' if slope_ok else 'INAPPROPRIATE'} to employ ANCOVA. "
        f"The adjusted means and standard error were {parts_en}. "
        f"The post-test scores were {'significantly different' if p_grp < alpha else 'not significantly different'} "
        f"(F = {round(f_grp,2)}, {grp_txt_en}). "
        f"Furthermore, the effect size (η²) was {round(grp_eta2,3)}, indicating a {mag} effect (Cohen, 1988)."
    )
    parts_zh = "、".join(
        f"{g} 為 {round(float(adj_map[g]['調整後平均數']),2)}（SE={round(float(adj_map[g]['標準誤']),2)}）"
        for g in groups
    )
    article_zh = (
        f"本研究採用 ANCOVA 檢驗各組後測分數是否有顯著差異。"
        f"Levene 檢定顯示變異數{'相等' if levene['同質(p≥α)'] else '不相等'}"
        f"（F = {levene['F']}, {lev_txt_en.replace('p','p')}）；"
        f"組內迴歸係數同質性檢定（交乘項 F = {slope_tbl['F'].iloc[0] if not slope_tbl.empty else float('nan')}, {slope_txt_en}），"
        f"{'符合' if slope_ok else '不符合'} ANCOVA 前提。"
        f"調整後平均數與標準誤：{parts_zh}。"
        f"各組後測分數{'有' if p_grp < alpha else '無'}顯著差異"
        f"（F = {round(f_grp,2)}, {grp_txt_en}），"
        f"效果量 η² = {round(grp_eta2,3)}，為{mag}（Cohen, 1988）。"
    )

    return AncovaResult(
        dv=dv, group=group, covars=list(covars), groups=groups, n_total=n_total,
        descriptives=desc, normality=normality, normality_ok=normality_ok,
        levene=levene, slope_homogeneity=slope_tbl, slope_ok=slope_ok,
        ancova_table=ancova_table, r_squared=round(r2, 3), r_squared_adj=round(r2_adj, 3),
        adjusted_means=adj, summary_apa=summary_apa,
        group_F=round(f_grp, 3), group_p=round(p_grp, 4),
        group_eta2=round(grp_eta2, 3), eta2_magnitude=mag,
        posthoc=posthoc, article_zh=article_zh, article_en=article_en,
        decisions=decisions, alpha=alpha, warnings=warnings,
    )
