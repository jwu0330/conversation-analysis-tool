"""序列分析核心邏輯（純函式，不依賴 Streamlit 或 src/core）。

流程：原始「一題一列」資料 → 清理 → 個人 Bloom 序列 → Lag-1 轉移表
→ 轉移矩陣 / 高低階轉移 / 題序剖面。
"""
from __future__ import annotations

import re

import pandas as pd

# 標準欄位名（模組內部統一使用）
STUDENT, GROUP, BLOOM, ORDER = "StudentID", "Group", "Bloom", "Order"


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
    seqs["序列字串"] = seqs["序列"].map(lambda xs: " → ".join(f"L{v}" for v in xs))
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
    idx = [f"L{v}" for v in levels]
    mat = pd.DataFrame(0.0, index=idx, columns=idx)
    for _, r in sub.iterrows():
        mat.loc[f"L{int(r['Source'])}", f"L{int(r['Target'])}"] = r["次數"]
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
        .agg(平均Bloom="mean", 人次="count")
        .reset_index()
        .rename(columns={GROUP: "組別"})
    )
    prof["平均Bloom"] = prof["平均Bloom"].round(2)
    return prof
