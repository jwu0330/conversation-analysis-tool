"""統計檢定：獨立樣本 t 檢定（含 Levene 判斷等變異 / Welch、Cohen's d）。

回傳統一結構的 TestResult，方便 UI 顯示與後續擴充。
（卡方等其他檢定已移到 ANCOVA / 敘述性統計頁對應功能，不再於此保留。）
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class TestResult:
    method: str                       # 檢定方法名稱
    applicable: str                   # 適用資料條件
    statistic: float                  # 檢定統計量
    p_value: float                    # p 值
    effect_size: dict = field(default_factory=dict)  # {名稱: 值}
    extra: dict = field(default_factory=dict)         # 自由度、樣本數等
    warnings: list[str] = field(default_factory=list)  # 注意事項
    interpretation: str = ""          # 中文解釋
    alpha: float = 0.05

    @property
    def significant(self) -> bool:
        return bool(self.p_value < self.alpha) if not np.isnan(self.p_value) else False


def _eta2_magnitude(e: float) -> str:
    """η² 效果量強度（Cohen 1988：.01/.059/.138）。"""
    if e != e:
        return "無法判定"
    if e < 0.01:
        return "極小"
    if e < 0.059:
        return "小效果"
    if e < 0.138:
        return "中效果"
    return "大效果"


def one_way_anova(
    df: pd.DataFrame,
    value_col: str,
    group_col: str,
    alpha: float = 0.05,
) -> TestResult:
    """一因子變異數分析（One-way ANOVA）：比較 3 組（含）以上的平均數是否不同。

    回傳 F、df、p、效果量 η²，附各組描述、Levene 同質性、Tukey HSD 事後比較。
    （2 組時 ANOVA 等同 t 檢定，仍可跑；本工具建議 2 組直接用 t 檢定。）
    """
    data = df[[value_col, group_col]].dropna().copy()
    data[value_col] = pd.to_numeric(data[value_col], errors="coerce")
    data = data.dropna()
    data[group_col] = data[group_col].astype(str)
    levels = sorted(data[group_col].unique())
    k = len(levels)

    if k < 2:
        return TestResult(
            method="一因子 ANOVA", applicable="一個 3 組以上的分類欄 + 一個數值欄",
            statistic=float("nan"), p_value=float("nan"),
            warnings=[f"分類欄只有 {k} 組，ANOVA 需至少 2 組。"],
            interpretation="組數不足，無法進行 ANOVA。", alpha=alpha,
        )
    samples = [data.loc[data[group_col] == g, value_col].to_numpy(float) for g in levels]
    if any(len(s) < 2 for s in samples):
        return TestResult(
            method="一因子 ANOVA", applicable="每組至少 2 筆",
            statistic=float("nan"), p_value=float("nan"),
            warnings=["有組別樣本數 < 2，無法估計組內變異。"],
            interpretation="有組別樣本過少。", alpha=alpha,
        )

    classic_f, classic_p = stats.f_oneway(*samples)
    grand = float(data[value_col].mean())
    n_total = len(data)
    ss_between = float(sum(len(s) * (s.mean() - grand) ** 2 for s in samples))
    ss_within = float(sum(((s - s.mean()) ** 2).sum() for s in samples))
    ss_total = ss_between + ss_within
    df_b, df_w = k - 1, n_total - k
    eta2 = ss_between / ss_total if ss_total > 0 else float("nan")
    mag = _eta2_magnitude(eta2)

    lev_stat, lev_p = stats.levene(*samples, center="mean")
    warnings: list[str] = []
    use_welch = bool(lev_p < alpha)
    if use_welch:
        import pingouin as pg
        welch = pg.welch_anova(data=data, dv=value_col, between=group_col).iloc[0]
        p_col = "p-unc" if "p-unc" in welch.index else "p_unc"
        f_stat, p = float(welch["F"]), float(welch[p_col])
        df_b_display, df_w_display = float(welch["ddof1"]), float(welch["ddof2"])
    else:
        f_stat, p = float(classic_f), float(classic_p)
        df_b_display, df_w_display = df_b, df_w
    if lev_p < alpha:
        warnings.append(f"Levene p = {lev_p:.4f} < {alpha}：已自動改用 Welch ANOVA，"
                        "事後比較改用 Games-Howell。")

    desc = (
        data.groupby(group_col)[value_col]
        .agg(n="count", 平均="mean", 標準差="std").round(3)
        .reset_index().rename(columns={group_col: "組別"})
    )
    anova_tbl = pd.DataFrame([
        {"來源": "組間（Welch 修正）" if use_welch else "組間", "平方和": round(ss_between, 3),
         "自由度": round(df_b_display, 3),
         "平均平方": None if use_welch else (round(ss_between / df_b, 3) if df_b else None),
         "F": round(float(f_stat), 4), "p值": round(float(p), 4), "η²": round(eta2, 3)},
        {"來源": "組內", "平方和": round(ss_within, 3), "自由度": round(df_w_display, 3),
         "平均平方": None if use_welch else (round(ss_within / df_w, 3) if df_w else None),
         "F": None, "p值": None, "η²": None},
        {"來源": "總和", "平方和": round(ss_total, 3), "自由度": n_total - 1,
         "平均平方": None, "F": None, "p值": None, "η²": None},
    ])

    tukey_df = None
    try:
        if use_welch:
            import pingouin as pg
            tukey_df = pg.pairwise_gameshowell(data=data, dv=value_col, between=group_col)
        else:
            from statsmodels.stats.multicomp import pairwise_tukeyhsd
            tuk = pairwise_tukeyhsd(data[value_col].to_numpy(float),
                                    data[group_col].to_numpy(), alpha=alpha)
            tukey_df = pd.DataFrame(tuk._results_table.data[1:],
                                    columns=tuk._results_table.data[0])
    except Exception:  # noqa: BLE001
        pass

    sig = "達統計顯著" if p < alpha else "未達統計顯著"
    interp = (
        f"共 {k} 組、總樣本 {n_total}。"
        f"{'Welch ' if use_welch else ''}F({df_b_display:.0f}, {df_w_display:.2f}) = {f_stat:.3f}，p = {p:.4f}，{sig}"
        f"（α = {alpha}）。效果量 η² = {eta2:.3f}（{mag}）。"
        + ((f"各組平均數間存在顯著差異，詳見{'Games-Howell' if use_welch else 'Tukey HSD'}事後比較。") if p < alpha
           else "尚無足夠證據顯示各組平均數有差異。")
    )
    return TestResult(
        method="Welch 一因子 ANOVA" if use_welch else "一因子變異數分析 One-way ANOVA",
        applicable="一個分類欄（≥3 組佳）+ 一個連續數值欄；無共變量",
        statistic=float(f_stat), p_value=float(p),
        effect_size={"η²": float(eta2), "強度": mag},
        extra={
            "組數": k, "總樣本": n_total, "df組間": df_b, "df組內": df_w,
            "Levene_F": round(float(lev_stat), 3), "Levene_p": round(float(lev_p), 4),
            "採用方法": "Welch ANOVA + Games-Howell" if use_welch else "傳統 ANOVA + Tukey HSD",
            "描述統計": desc, "ANOVA表": anova_tbl, "Tukey事後": tukey_df,
        },
        warnings=warnings, interpretation=interp, alpha=alpha,
    )


def friedman_count_test(
    df: pd.DataFrame, unit_col: str, category_col: str, alpha: float = 0.05
) -> TestResult:
    """同一觀察單位跨多類別的計數比較；使用 Friedman 重複量數檢定。"""
    grid = df.groupby([unit_col, category_col]).size().unstack(fill_value=0)
    if grid.shape[0] < 2 or grid.shape[1] < 3:
        return TestResult(
            method="Friedman 重複量數檢定", applicable="至少 2 個觀察單位、3 個類別",
            statistic=float("nan"), p_value=float("nan"),
            warnings=["Friedman 檢定至少需要 2 個觀察單位與 3 個類別。"],
            interpretation="資料量不足，無法執行 Friedman 檢定。", alpha=alpha,
        )
    stat, p = stats.friedmanchisquare(*(grid[c].to_numpy(float) for c in grid.columns))
    n, k = grid.shape
    kendall_w = float(stat / (n * (k - 1)))
    sig = "達統計顯著" if p < alpha else "未達統計顯著"
    return TestResult(
        method="Friedman 重複量數檢定",
        applicable="同一觀察單位在 3 個以上類別的計數比較",
        statistic=float(stat), p_value=float(p),
        effect_size={"Kendall's W": kendall_w},
        extra={"觀察單位數": n, "類別數": k, "自由度": k - 1, "計數矩陣": grid.reset_index()},
        interpretation=(f"χ²({k - 1}) = {stat:.3f}，p = {p:.4f}，{sig}；"
                        f"Kendall's W = {kendall_w:.3f}。"), alpha=alpha,
    )


def _cohens_d_magnitude(d: float) -> str:
    d = abs(d)
    if np.isnan(d):
        return "無法判定"
    if d < 0.2:
        return "極小效果"
    if d < 0.5:
        return "小效果"
    if d < 0.8:
        return "中等效果"
    return "大效果"


def independent_t_test(
    df: pd.DataFrame,
    value_col: str,
    group_col: str,
    alpha: float = 0.05,
) -> TestResult:
    """獨立樣本 t 檢定：比較兩組在某數值欄位的平均數是否不同。

    自動做 Levene 變異數同質性檢定，決定用 Student's t（等變異）或 Welch t（不等變異），
    並回報 Cohen's d 效果量。
    """
    data = df[[value_col, group_col]].dropna().copy()
    data[value_col] = pd.to_numeric(data[value_col], errors="coerce")
    data = data.dropna()
    groups = list(data[group_col].astype(str).unique())

    if len(groups) != 2:
        return TestResult(
            method="獨立樣本 t 檢定",
            applicable="分組欄位需剛好 2 組；數值欄位為連續變數",
            statistic=float("nan"),
            p_value=float("nan"),
            warnings=[f"分組欄位有 {len(groups)} 組，t 檢定需剛好 2 組（3 組以上請用 ANCOVA/ANOVA）。"],
            interpretation="組數不符，無法進行獨立樣本 t 檢定。",
            alpha=alpha,
        )

    g0 = data.loc[data[group_col].astype(str) == groups[0], value_col].to_numpy(float)
    g1 = data.loc[data[group_col].astype(str) == groups[1], value_col].to_numpy(float)

    warnings: list[str] = []
    lev_stat, lev_p = stats.levene(g0, g1, center="mean")
    equal_var = lev_p >= alpha
    method_txt = "Student's t（等變異）" if equal_var else "Welch's t（不等變異）"
    if not equal_var:
        warnings.append(
            f"Levene 檢定 p = {lev_p:.4f} < {alpha}，兩組變異數不同質，改用 Welch's t。"
        )

    t_stat, p = stats.ttest_ind(g0, g1, equal_var=equal_var)

    # Cohen's d（用合併標準差）
    n0, n1 = len(g0), len(g1)
    sp = np.sqrt(((n0 - 1) * g0.var(ddof=1) + (n1 - 1) * g1.var(ddof=1)) / (n0 + n1 - 2))
    d = (g0.mean() - g1.mean()) / sp if sp > 0 else float("nan")
    mag = _cohens_d_magnitude(d)

    if min(n0, n1) < 15:
        warnings.append(f"最小組樣本數僅 {min(n0, n1)}，樣本偏少，常態假設下結果需謹慎。")

    sig_txt = "達統計顯著" if p < alpha else "未達統計顯著"
    interp = (
        f"{groups[0]} 平均 = {g0.mean():.3f}（n={n0}）、{groups[1]} 平均 = {g1.mean():.3f}"
        f"（n={n1}）。t = {t_stat:.3f}，p = {p:.4f}，{sig_txt}（α = {alpha}）。"
        f"效果量 Cohen's d = {d:.3f}（{mag}）。"
    )

    return TestResult(
        method=f"獨立樣本 t 檢定（{method_txt}）",
        applicable="一個 2 類別分組欄位 + 一個連續數值欄位",
        statistic=float(t_stat),
        p_value=float(p),
        effect_size={"Cohen's d": float(d), "強度": mag},
        extra={
            "組別": groups,
            f"{groups[0]}_平均": round(float(g0.mean()), 4),
            f"{groups[1]}_平均": round(float(g1.mean()), 4),
            f"{groups[0]}_n": n0,
            f"{groups[1]}_n": n1,
            "Levene_p": round(float(lev_p), 4),
            "採用方法": method_txt,
        },
        warnings=warnings,
        interpretation=interp,
        alpha=alpha,
    )
