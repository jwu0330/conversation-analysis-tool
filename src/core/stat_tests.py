"""統計檢定。

MVP 提供卡方獨立性檢定 + Cramér's V 效果量。
每個檢定回傳統一結構的 TestResult，方便 UI 顯示與 v2（t 檢定、ANOVA、
非參數檢定、相關分析）沿用相同格式擴充。
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


def cramers_v(confusion_matrix: np.ndarray) -> float:
    """由卡方值計算 Cramér's V 效果量（含偏誤校正）。"""
    chi2 = stats.chi2_contingency(confusion_matrix, correction=False)[0]
    n = confusion_matrix.sum()
    if n == 0:
        return float("nan")
    phi2 = chi2 / n
    r, k = confusion_matrix.shape
    phi2corr = max(0, phi2 - ((k - 1) * (r - 1)) / (n - 1))
    rcorr = r - ((r - 1) ** 2) / (n - 1)
    kcorr = k - ((k - 1) ** 2) / (n - 1)
    denom = min((kcorr - 1), (rcorr - 1))
    if denom <= 0:
        return float("nan")
    return float(np.sqrt(phi2corr / denom))


def _cramers_v_magnitude(v: float, dof_min: int) -> str:
    """依 Cohen 標準判斷 Cramér's V 強度（隨自由度調整門檻）。"""
    if np.isnan(v):
        return "無法判定"
    # Cohen 針對 df=1 的門檻：0.1 小 / 0.3 中 / 0.5 大
    small, medium, large = 0.1, 0.3, 0.5
    if dof_min >= 2:
        small, medium, large = 0.07, 0.21, 0.35
    if dof_min >= 3:
        small, medium, large = 0.06, 0.17, 0.29
    if v < small:
        return "幾乎無關聯"
    if v < medium:
        return "小效果"
    if v < large:
        return "中等效果"
    return "大效果"


def chi_square_test(
    df: pd.DataFrame,
    col_a: str,
    col_b: str,
    alpha: float = 0.05,
) -> TestResult:
    """卡方獨立性檢定：檢驗兩個類別欄位的分布是否有關聯。"""
    data = df[[col_a, col_b]].dropna()
    observed = pd.crosstab(data[col_a], data[col_b])

    warnings: list[str] = []
    if observed.shape[0] < 2 or observed.shape[1] < 2:
        return TestResult(
            method="卡方獨立性檢定",
            applicable="兩個皆為類別欄位，且各至少 2 個類別",
            statistic=float("nan"),
            p_value=float("nan"),
            warnings=["兩個欄位其中之一少於 2 個類別，無法進行卡方檢定。"],
            interpretation="資料不足以進行卡方檢定。",
            alpha=alpha,
        )

    chi2, p, dof, expected = stats.chi2_contingency(observed)
    n = int(observed.values.sum())
    v = cramers_v(observed.values)
    dof_min = min(observed.shape) - 1
    magnitude = _cramers_v_magnitude(v, dof_min)

    # 期望次數檢查（卡方基本假設）
    low_cells = int((expected < 5).sum())
    total_cells = expected.size
    if low_cells > 0:
        pct = low_cells / total_cells * 100
        warnings.append(
            f"有 {low_cells}/{total_cells} 格（{pct:.0f}%）期望次數 < 5，"
            "可能違反卡方假設，建議合併類別或改用 Fisher 精確檢定。"
        )
    if n < 20:
        warnings.append(f"總樣本數僅 {n}，樣本偏少，結果需謹慎解讀。")

    sig_txt = "達統計顯著" if p < alpha else "未達統計顯著"
    interp = (
        f"卡方值 = {chi2:.3f}，自由度 = {dof}，p = {p:.4f}，{sig_txt}"
        f"（α = {alpha}）。效果量 Cramér's V = {v:.3f}（{magnitude}）。"
    )
    if p < alpha:
        interp += f"表示「{col_a}」與「{col_b}」的分布之間存在統計上顯著的關聯。"
    else:
        interp += f"尚無足夠證據顯示「{col_a}」與「{col_b}」的分布有關聯。"

    return TestResult(
        method="卡方獨立性檢定 (Chi-square test of independence)",
        applicable="兩個皆為類別欄位；每格期望次數建議 ≥ 5",
        statistic=float(chi2),
        p_value=float(p),
        effect_size={"Cramér's V": float(v), "強度": magnitude},
        extra={
            "自由度": int(dof),
            "樣本數": n,
            "觀察次數表": observed,
            "期望次數表": pd.DataFrame(
                np.round(expected, 2), index=observed.index, columns=observed.columns
            ),
        },
        warnings=warnings,
        interpretation=interp,
        alpha=alpha,
    )
