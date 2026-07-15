"""統計分析頁：SPSS 式共變數分析 ANCOVA（一鍵預設流程）。

預設路徑：依變數＝數值後測、組別＝實驗/對照、共變量＝前測。按「一鍵執行」就跑完
SPSS 完整流程（描述 → 變異數同質 → 斜率同質 → 型 III ANCOVA → 調整後平均 → 事後比較）。
進階設定可改依變數/組別/共變量與顯著水準；未展開時一律用預設。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import state
from src.core import ancova, column_types

st.set_page_config(page_title="統計分析", page_icon="📐", layout="wide")
st.title("📐 統計分析（共變數分析 ANCOVA）")
st.caption("仿 SPSS「一般線性模型 → 單變量」：控制共變量後，比較各組調整後平均數是否不同。")

df = state.require_data()
num_cols = column_types.numeric_columns(df)
cat_cols = column_types.categorical_columns(df)

if not num_cols or not cat_cols:
    st.warning("ANCOVA 需要：至少 1 個類別欄位（組別）、至少 2 個數值欄位（依變數＋共變量）。")
    st.stop()


def _guess(cands: list[str], keys: list[str], fallback_idx: int = 0) -> str:
    for kw in keys:
        for c in cands:
            if kw in str(c).lower():
                return c
    return cands[fallback_idx] if cands else ""


# 預設路徑（可在進階設定覆蓋）：後測=依變數、前測=共變量、組別=實驗/對照
default_dv = _guess(num_cols, ["後測", "post", "成績", "score"], -1)
default_cov = _guess([c for c in num_cols if c != default_dv] or num_cols,
                     ["前測", "pre", "先備"], 0)
default_group = _guess(cat_cols, ["組別", "group", "班級", "class", "實驗"], 0)

# ── 進階設定（編輯預設）───────────────────────────────────
with st.expander("⚙️ 進階設定（編輯預設變數與參數；不展開就用預設路徑）"):
    dv = st.selectbox("依變數（連續，通常＝後測）", num_cols,
                      index=num_cols.index(default_dv) if default_dv in num_cols else 0)
    group = st.selectbox("固定因子／組別（類別，例：實驗vs對照、班級、前後測）",
                         cat_cols,
                         index=cat_cols.index(default_group) if default_group in cat_cols else 0)
    cov_opts = [c for c in num_cols if c != dv]
    default_covs = [default_cov] if default_cov in cov_opts else cov_opts[:1]
    covars = st.multiselect("共變量（連續，通常＝前測，可多選）", cov_opts,
                            default=default_covs)
    alpha = st.selectbox("顯著水準 α", [0.05, 0.01, 0.10], index=0)

# expander 未展開時上面變數已用預設；補在 expander 外的一鍵按鈕
st.info(
    f"目前設定 →　依變數：**{dv}**　｜　組別：**{group}**　｜　"
    f"共變量：**{', '.join(covars) if covars else '（尚未選）'}**　｜　α = {alpha}"
)

if st.button("▶️ 一鍵執行 ANCOVA（跑完整 SPSS 流程）", type="primary"):
    if not covars:
        st.error("請至少選一個共變量（到進階設定選）。")
        st.stop()
    try:
        res = ancova.run_ancova(df, dv, group, covars, alpha=alpha)
    except Exception as err:  # noqa: BLE001
        st.error(f"ANCOVA 執行失敗：{err}")
        st.stop()

    st.success(f"完成：{group} 共 {len(res.groups)} 組（{', '.join(res.groups)}），"
               f"有效樣本 n = {res.n_total}。")

    # 1. 描述統計
    st.subheader("① 各組描述統計")
    st.dataframe(res.descriptives, width="stretch", hide_index=True)
    state.register_export_table("ANCOVA_1_描述統計", res.descriptives)

    # 2. 變異數同質性
    st.subheader("② 變異數同質性檢定（Levene）")
    lv = res.levene
    cols = st.columns(3)
    cols[0].metric("Levene W", lv["統計量W"])
    cols[1].metric("p 值", lv["p值"])
    cols[2].metric("變異數同質", "✅ 是" if lv["同質(p≥α)"] else "⚠️ 否")
    state.register_export_table("ANCOVA_2_Levene",
                                pd.DataFrame([lv]))

    # 3. 迴歸斜率同質性
    st.subheader("③ 迴歸斜率同質性檢定（前提假設）")
    st.caption("檢定「組別 × 共變量」交互作用。p ≥ α 代表各組斜率一致，符合 ANCOVA 前提。")
    st.dataframe(res.slope_homogeneity, width="stretch", hide_index=True)
    if res.slope_ok:
        st.success("✅ 斜率同質假設成立，ANCOVA 適用。")
    else:
        st.warning("⚠️ 斜率不同質，交互作用顯著 —— ANCOVA 前提被違反，主分析結果需保留。")
    state.register_export_table("ANCOVA_3_斜率同質性", res.slope_homogeneity)

    # 4. 主 ANCOVA 表
    st.subheader("④ 主分析：ANCOVA 摘要表（型 III 平方和）")
    st.dataframe(res.ancova_table, width="stretch", hide_index=True)
    grp_row = res.ancova_table[res.ancova_table["來源"].str.startswith("組別")]
    if not grp_row.empty:
        p = grp_row.iloc[0]["p值"]
        eta = grp_row.iloc[0]["淨η²"]
        if p is not None and p < alpha:
            st.success(f"✅ 控制共變量後，組別主效果顯著（p = {p}，淨η² = {eta}）：各組調整後平均數有差異。")
        elif p is not None:
            st.info(f"ℹ️ 控制共變量後，組別主效果未達顯著（p = {p}）。")
    state.register_export_table("ANCOVA_4_主分析表", res.ancova_table)

    # 5. 調整後平均數
    st.subheader("⑤ 調整後平均數（EMMeans）")
    st.caption(res.adjusted_means.attrs.get("說明", ""))
    st.dataframe(res.adjusted_means, width="stretch", hide_index=True)
    state.register_export_table("ANCOVA_5_調整後平均", res.adjusted_means)

    # 6. 事後比較
    st.subheader("⑥ 事後兩兩比較（調整後平均數，Bonferroni 校正）")
    if len(res.groups) <= 2:
        st.caption("僅兩組，主分析即為兩組比較，事後比較供對照。")
    st.dataframe(res.posthoc, width="stretch", hide_index=True)
    state.register_export_table("ANCOVA_6_事後比較", res.posthoc)

    if res.warnings:
        st.warning("**注意事項**\n\n" + "\n".join(f"- {w}" for w in res.warnings))
    st.caption("以上結果已加入匯出清單，可回「首頁 → 匯出」一併下載。")
else:
    st.caption("設定好變數後，按上方「▶️ 一鍵執行 ANCOVA」。預設路徑會自動帶入前測／後測／組別。")
