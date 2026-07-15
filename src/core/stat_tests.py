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
