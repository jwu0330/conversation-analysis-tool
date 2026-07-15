"""序列分析核心邏輯（純函式，不依賴 Streamlit 或 src/core）。

流程：原始「一題一列」資料 → 清理 → 個人 Bloom 序列 → Lag-1 轉移表
→ 轉移矩陣 / 高低階轉移 / 題序剖面。
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy import stats

# 標準欄位名（模組內部統一使用）
STUDENT, GROUP, BLOOM, ORDER = "StudentID", "Group", "Bloom", "Order"

# SOLO 顯示標籤：層級數字(=SOLO_Score) → 字母，方便對照「第幾層＋結構代號」。
# P=前結構、U=單點、M=多點、R=關聯、EA=延伸抽象。
_SOLO_LETTER = {0: "P", 1: "U", 2: "M", 3: "R", 4: "EA"}


def level_label(v: int) -> str:
    """把層級數字轉成顯示標籤，例如 3 → 'S3·R'（第 3 層、關聯結構）。

    未知層級（超出 0–4）退回 'S{v}'，計算不受影響、只影響畫面顯示。
    """
    v = int(v)
    letter = _SOLO_LETTER.get(v)
    return f"S{v}·{letter}" if letter else f"S{v}"


def parse_bloom_level(value) -> int | None:
    """把各種寫法的 Bloom 標記轉成整數 Level。

    支援："Level 4"、"L4"、"L0"、4、"4" → 4 / 0；無法解析回傳 None。
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    m = re.search(r"\d+", str(value))
    return int(m.group()) if m else None


def guess_columns(columns: list[str]) -> dict[str, str | None]:
    """依欄位名稱猜測 student / group / bloom / order 對應欄位。"""
    lower = {c: str(c).lower() for c in columns}

    def find(keywords: list[str]) -> str | None:
        # 依關鍵字優先序尋找：先找較明確的字（如「學生」）再找通用字（如「id」），
        # 避免「對話ID」因含 id 被誤判為學生欄位。
        for kw in keywords:
            for col, low in lower.items():
                if kw in low or kw in str(col):
                    return col
        return None

    return {
        "student": find(["學生", "student", "sid", "id"]),
        "group": find(["組別", "group", "組"]),
        "bloom": find(["bloom", "層級", "level"]),
        "order": find(["order", "題序", "序號", "對話", "create", "序", "time", "時間"]),
    }


def prepare(
    df: pd.DataFrame,
    student_col: str,
    group_col: str,
    bloom_col: str,
    order_col: str,
    include_l0: bool = True,
) -> pd.DataFrame:
    """整理成標準四欄，解析 Bloom Level，去除必要欄位缺漏的列。"""
    work = df[[student_col, group_col, bloom_col, order_col]].copy()
    work.columns = [STUDENT, GROUP, BLOOM, ORDER]
    work[BLOOM] = work[BLOOM].map(parse_bloom_level)
    work = work.dropna(subset=[STUDENT, GROUP, BLOOM, ORDER])
    work[BLOOM] = work[BLOOM].astype(int)
    if not include_l0:
        work = work[work[BLOOM] != 0]
    return work.reset_index(drop=True)


def _ordered(work: pd.DataFrame) -> pd.DataFrame:
    return work.sort_values([STUDENT, ORDER], kind="stable")


def build_sequences(work: pd.DataFrame) -> pd.DataFrame:
    """每位學生一條依時間排序的 Bloom 序列。"""
    seqs = (
        _ordered(work)
        .groupby([STUDENT, GROUP], sort=False)[BLOOM]
        .apply(list)
        .reset_index(name="序列")
    )
    seqs["序列字串"] = seqs["序列"].map(lambda xs: " → ".join(level_label(v) for v in xs))
    seqs["提問數"] = seqs["序列"].map(len)
    return seqs.rename(columns={STUDENT: "學生", GROUP: "組別"})


def transitions(work: pd.DataFrame) -> pd.DataFrame:
    """Lag-1 轉移表：每位學生相鄰兩題的 (Source→Target)，依組別彙整次數。"""
    rows: list[tuple] = []
    for (_, grp), sub in _ordered(work).groupby([STUDENT, GROUP], sort=False):
        levels = sub[BLOOM].tolist()
        for src, tgt in zip(levels[:-1], levels[1:]):
            rows.append((grp, src, tgt))
    if not rows:
        return pd.DataFrame(columns=["組別", "Source", "Target", "次數"])
    t = pd.DataFrame(rows, columns=["組別", "Source", "Target"])
    out = (
        t.groupby(["組別", "Source", "Target"]).size().reset_index(name="次數")
    )
    return out.sort_values(["組別", "次數"], ascending=[True, False]).reset_index(drop=True)


def all_levels(work: pd.DataFrame) -> list[int]:
    return sorted(work[BLOOM].unique().tolist())


def transition_matrix(
    trans: pd.DataFrame,
    group: str,
    levels: list[int],
    normalize: bool = False,
) -> pd.DataFrame:
    """把某組的轉移表攤成 Source×Target 方陣（次數或列機率）。"""
    sub = trans[trans["組別"] == group]
    idx = [level_label(v) for v in levels]
    mat = pd.DataFrame(0.0, index=idx, columns=idx)
    for _, r in sub.iterrows():
        mat.loc[level_label(int(r['Source'])), level_label(int(r['Target']))] = r["次數"]
    if normalize:
        row_sum = mat.sum(axis=1).replace(0, pd.NA)
        mat = (mat.div(row_sum, axis=0) * 100).round(1).fillna(0.0)
    return mat


def high_low_transitions(
    work: pd.DataFrame, high_min: int = 4
) -> pd.DataFrame:
    """把 Level 併成高/低階後統計四種轉移（低→低、低→高、高→高、高→低）。"""
    def band(level: int) -> str:
        return "高階" if level >= high_min else "低階"

    rows: list[tuple] = []
    for (_, grp), sub in _ordered(work).groupby([STUDENT, GROUP], sort=False):
        levels = sub[BLOOM].tolist()
        for src, tgt in zip(levels[:-1], levels[1:]):
            rows.append((grp, band(src), band(tgt)))
    if not rows:
        return pd.DataFrame(columns=["組別", "Source", "Target", "次數", "組內比例(%)"])
    t = pd.DataFrame(rows, columns=["組別", "Source", "Target"])
    out = t.groupby(["組別", "Source", "Target"]).size().reset_index(name="次數")
    totals = out.groupby("組別")["次數"].transform("sum")
    out["組內比例(%)"] = (out["次數"] / totals * 100).round(1)
    return out


def position_profile(work: pd.DataFrame) -> pd.DataFrame:
    """題序剖面：各組在第 1、2、3… 題的平均 Bloom Level。"""
    w = _ordered(work).copy()
    w["題序"] = w.groupby([STUDENT], sort=False).cumcount() + 1
    prof = (
        w.groupby([GROUP, "題序"])[BLOOM]
        .agg(平均SOLO="mean", 人次="count")
        .reset_index()
        .rename(columns={GROUP: "組別"})
    )
    prof["平均SOLO"] = prof["平均SOLO"].round(2)
    return prof


# ---------------------------------------------------------------------------
# GSEQ 式滯後序列分析（Lag-1）
#
# 公式（Bakeman & Gottman, 1997；Allison & Liker, 1982 的調整殘差）：
#   令 O = 轉移次數矩陣（列=前題 Source，欄=後題 Target），N = 總轉移數，
#   R_i = 第 i 列總和（從 i 出發的轉移數），C_j = 第 j 欄總和（進入 j 的轉移數）。
#
#   期望次數     E_ij = R_i * C_j / N
#   轉移機率     P_ij = O_ij / R_i                （P(下一題=j | 前一題=i)）
#   調整後殘差   z_ij = (O_ij - E_ij) / sqrt( E_ij * (1 - R_i/N) * (1 - C_j/N) )
#   雙尾 p 值    p_ij = 2 * (1 - Φ(|z_ij|))
#   顯著判準     |z| > z_crit（α=0.05 時 z_crit≈1.96）→ 該轉移顯著偏多/偏少
# ---------------------------------------------------------------------------


def gseq_stats(
    trans: pd.DataFrame,
    group: str,
    levels: list[int],
    alpha: float = 0.05,
) -> pd.DataFrame:
    """對單一組別計算 GSEQ 式滯後序列統計（長格式，一列一個轉移）。

    欄位：組別、Source、Target、觀察次數、期望次數、轉移機率、調整殘差z、p值、顯著。
    """
    obs = transition_matrix(trans, group, levels, normalize=False)
    idx = list(obs.index)
    o_mat = obs.to_numpy(dtype=float)
    n = float(o_mat.sum())
    row_tot = o_mat.sum(axis=1)
    col_tot = o_mat.sum(axis=0)
    z_crit = float(stats.norm.ppf(1 - alpha / 2))

    records: list[dict] = []
    for i, s_lab in enumerate(idx):
        for j, t_lab in enumerate(idx):
            o = o_mat[i, j]
            e = row_tot[i] * col_tot[j] / n if n > 0 else float("nan")
            p_trans = o / row_tot[i] if row_tot[i] > 0 else float("nan")
            var = e * (1 - row_tot[i] / n) * (1 - col_tot[j] / n) if n > 0 else float("nan")
            z = (o - e) / np.sqrt(var) if (var is not None and var > 0) else float("nan")
            low_e = bool(e == e and e < 5)  # 期望次數 < 5：z 的常態近似不可靠
            if np.isnan(z):
                p_val, sig = float("nan"), ""
            else:
                p_val = float(2 * (1 - stats.norm.cdf(abs(z))))
                # 顯著偏多(↑)才是滯後序列分析主要解讀的「真實模式」；
                # 偏少(↓)一般不下結論，另欄標示、預設不強調。
                sig = "↑ 顯著偏多" if z >= z_crit else "↓ 顯著偏少" if z <= -z_crit else ""
            records.append(
                {
                    "組別": group,
                    "Source": s_lab,
                    "Target": t_lab,
                    "觀察次數": int(o),
                    "期望次數": round(e, 2) if e == e else None,
                    "轉移機率": round(p_trans, 3) if p_trans == p_trans else None,
                    "調整殘差z": round(z, 2) if z == z else None,
                    "p值": round(p_val, 4) if p_val == p_val else None,
                    "顯著": sig,
                    "可信度": "低(期望<5)" if low_e else "",
                }
            )
    return pd.DataFrame.from_records(records)


def gseq_all_groups(
    trans: pd.DataFrame,
    groups: list[str],
    levels: list[int],
    alpha: float = 0.05,
) -> pd.DataFrame:
    """對所有組別計算 GSEQ 統計並合併。"""
    frames = [gseq_stats(trans, g, levels, alpha) for g in groups]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def analyze(
    df: pd.DataFrame,
    student_col: str,
    group_col: str,
    bloom_col: str,
    order_col: str,
    *,
    include_l0: bool = True,
    high_min: int = 4,
    alpha: float = 0.05,
) -> dict:
    """一次跑完整條序列分析管線，回傳所有結果。

    這是「抽象出來的共用邏輯」：Streamlit 網頁與獨立 CLI 都呼叫此函式，
    因此兩邊算出的數字必然一致（同一份程式碼、同一組參數）。
    """
    work = prepare(df, student_col, group_col, bloom_col, order_col, include_l0=include_l0)
    levels = all_levels(work)
    groups = sorted(work[GROUP].unique().tolist()) if not work.empty else []
    trans = transitions(work)
    return {
        "work": work,
        "levels": levels,
        "groups": groups,
        "sequences": build_sequences(work),
        "transitions": trans,
        "matrices": {g: transition_matrix(trans, g, levels) for g in groups},
        "gseq": gseq_all_groups(trans, groups, levels, alpha),
        "highlow": high_low_transitions(work, high_min=high_min),
        "profile": position_profile(work),
        "points": position_points(work),
        "regressions": regression_by_group(work),
        "student_slopes": student_slopes(work),
        "params": {
            "student_col": student_col,
            "group_col": group_col,
            "bloom_col": bloom_col,
            "order_col": order_col,
            "include_l0": include_l0,
            "high_min": high_min,
            "alpha": alpha,
        },
    }


# ---------------------------------------------------------------------------
# 題序 × Bloom Level 趨勢／軌跡分析（線性迴歸）
#
#   對每一組（或每一位學生）以「題序 x」預測「Bloom Level y」做簡單線性迴歸：
#       ŷ = a + b·x
#   斜率 b > 0 且顯著 → 提問隨時間逐步深化。
#   平均反應線的 95% 信賴區帶：ŷ ± t(1-α/2, n-2) · s · sqrt(1/n + (x-x̄)²/Sxx)
# ---------------------------------------------------------------------------


def position_points(work: pd.DataFrame) -> pd.DataFrame:
    """每一題一列，附上該生的題序（第幾題），供散布圖與迴歸使用。"""
    w = _ordered(work).copy()
    w["題序"] = w.groupby([STUDENT], sort=False).cumcount() + 1
    return w[[STUDENT, GROUP, "題序", BLOOM]].rename(
        columns={STUDENT: "學生", GROUP: "組別", BLOOM: "Bloom"}
    )


def regression_by_group(work: pd.DataFrame) -> pd.DataFrame:
    """各組「題序→Bloom」線性迴歸：斜率、截距、R²、p 值、樣本數。"""
    pts = position_points(work)
    rows: list[dict] = []
    for g, sub in pts.groupby("組別", sort=True):
        if len(sub) >= 3 and sub["題序"].nunique() >= 2:
            res = stats.linregress(sub["題序"].to_numpy(float), sub["Bloom"].to_numpy(float))
            rows.append(
                {
                    "組別": g,
                    "斜率": round(float(res.slope), 4),
                    "截距": round(float(res.intercept), 3),
                    "R²": round(float(res.rvalue) ** 2, 3),
                    "p值": round(float(res.pvalue), 4),
                    "顯著": "是" if res.pvalue < 0.05 else "否",
                    "n": int(len(sub)),
                }
            )
        else:
            rows.append({"組別": g, "斜率": None, "截距": None, "R²": None,
                         "p值": None, "顯著": "-", "n": int(len(sub))})
    return pd.DataFrame(rows)


def regression_band(
    work: pd.DataFrame, group: str, alpha: float = 0.05, n_grid: int = 60
) -> dict | None:
    """回傳某組迴歸線與 95% 信賴區帶的座標（x, y_fit, lo, hi）；不足以迴歸則回 None。"""
    pts = position_points(work)
    sub = pts[pts["組別"] == group]
    x = sub["題序"].to_numpy(float)
    y = sub["Bloom"].to_numpy(float)
    n = len(x)
    if n < 3 or np.ptp(x) == 0:
        return None
    res = stats.linregress(x, y)
    x_bar = x.mean()
    sxx = float(((x - x_bar) ** 2).sum())
    resid = y - (res.intercept + res.slope * x)
    s = float(np.sqrt((resid ** 2).sum() / (n - 2)))
    t_crit = float(stats.t.ppf(1 - alpha / 2, n - 2))
    xg = np.linspace(x.min(), x.max(), n_grid)
    y_fit = res.intercept + res.slope * xg
    se = s * np.sqrt(1.0 / n + (xg - x_bar) ** 2 / sxx) if sxx > 0 else np.zeros_like(xg)
    return {
        "x": xg,
        "y": y_fit,
        "lo": y_fit - t_crit * se,
        "hi": y_fit + t_crit * se,
        "slope": float(res.slope),
    }


def student_slopes(work: pd.DataFrame, min_points: int = 3) -> pd.DataFrame:
    """每位學生自己的「題序→Bloom」迴歸斜率（至少 min_points 題才計），供箱型圖比較。"""
    pts = position_points(work)
    rows: list[dict] = []
    for (sid, g), sub in pts.groupby(["學生", "組別"], sort=False):
        if len(sub) >= min_points and sub["題序"].nunique() >= 2:
            res = stats.linregress(sub["題序"].to_numpy(float), sub["Bloom"].to_numpy(float))
            rows.append({"學生": sid, "組別": g, "斜率": round(float(res.slope), 4),
                         "提問數": int(len(sub))})
    return pd.DataFrame(rows)
