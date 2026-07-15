"""統計分析頁：SPSS 式共變數分析 ANCOVA（一鍵，完全對齊吳書豪《量化統計方法實作》講義）。

版面分兩區：
  ▍重要區（依講義順序，必報）：描述統計 → 常態性 → Levene → 斜率同質 →
      ANCOVA 型III 完整表 → 調整後平均數 → APA 彙整表
  ▍補充區（本工具加值）：效果量判準、事後 LSD、文章寫法、假設違反處理建議
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import state
from src.core import ancova, column_types

st.set_page_config(page_title="統計分析", page_icon="📐", layout="wide")
st.title("📐 統計分析（共變數分析 ANCOVA）")
st.caption("完全對照吳書豪《量化統計方法實作》SPSS 講義：前測=共變量、後測=依變數、組別=自變數，型 III 平方和。")

df = state.require_data()
num_cols = column_types.numeric_columns(df)
cat_cols = column_types.categorical_columns(df)

if not num_cols or not cat_cols:
    st.warning("ANCOVA 需要：至少 1 個類別欄位（組別）、至少 2 個數值欄位（後測＋前測）。")
    st.stop()


def _guess(cands: list[str], keys: list[str], fallback_idx: int = 0) -> str:
    for kw in keys:
        for c in cands:
            if kw in str(c).lower():
                return c
    return cands[fallback_idx] if cands else ""


default_dv = _guess(num_cols, ["後測", "post", "成績", "score"], -1)
default_cov = _guess([c for c in num_cols if c != default_dv] or num_cols, ["前測", "pre", "先備"], 0)
default_group = _guess(cat_cols, ["組別", "group", "班級", "class", "實驗"], 0)

with st.expander("⚙️ 進階設定（編輯預設變數與參數；不展開就用預設路徑）"):
    dv = st.selectbox("依變數（後測，連續）", num_cols,
                      index=num_cols.index(default_dv) if default_dv in num_cols else 0)
    group = st.selectbox("固定因子／組別（實驗vs對照、班級…）", cat_cols,
                         index=cat_cols.index(default_group) if default_group in cat_cols else 0)
    cov_opts = [c for c in num_cols if c != dv]
    default_covs = [default_cov] if default_cov in cov_opts else cov_opts[:1]
    covars = st.multiselect("共變量（前測，連續，可多選）", cov_opts, default=default_covs)
    alpha = st.selectbox("顯著水準 α", [0.05, 0.01, 0.10], index=0)

st.info(
    f"設定 →　依變數(後測)：**{dv}**　｜　組別：**{group}**　｜　"
    f"共變量(前測)：**{', '.join(covars) if covars else '（尚未選）'}**　｜　α = {alpha}"
)
st.caption("提醒（講義 p30）：前測**不要**單獨跑 t 檢定證明組別同質，直接以前測作共變量進 ANCOVA。")

if not st.button("▶️ 一鍵執行 ANCOVA（跑完整 SPSS 流程）", type="primary"):
    st.caption("按上方按鈕即依講義流程一次跑完。預設會自動帶入前測／後測／組別。")
    st.stop()

if not covars:
    st.error("請至少選一個共變量（前測）。到進階設定選。")
    st.stop()
try:
    res = ancova.run_ancova(df, dv, group, covars, alpha=alpha)
except Exception as err:  # noqa: BLE001
    st.error(f"ANCOVA 執行失敗：{err}")
    st.stop()

st.success(f"完成：{group} 共 {len(res.groups)} 組（{', '.join(res.groups)}），有效樣本 n = {res.n_total}。")

# ══════════════════════════ 重要區（依講義順序） ══════════════════════════
st.header("▍重要區（依講義流程與必報項目）")

# ① 描述統計
st.subheader("① 各組描述統計（N、平均數、標準差）")
st.dataframe(res.descriptives, width="stretch", hide_index=True)
state.register_export_table("ANCOVA_1_描述統計", res.descriptives)

# ② 常態性
st.subheader("② 常態性檢定（Shapiro-Wilk n<50／Kolmogorov-Smirnov n≥50）")
st.dataframe(res.normality, width="stretch", hide_index=True)
if res.normality_ok:
    st.success("✅ 各組皆通過常態性假設（p ≥ α）。")
else:
    st.warning("⚠️ 有組別未通過常態性 → 依講義改用無母數檢定（Mann-Whitney U）。")
state.register_export_table("ANCOVA_2_常態性", res.normality)

# ③ Levene
st.subheader("③ 變異數同質性檢定（Levene，以平均為中心）")
lv = res.levene
c = st.columns(4)
c[0].metric("F", lv["F"])
c[1].metric("df1 / df2", f"{lv['df1']} / {lv['df2']}")
c[2].metric("p 值", lv["p值"])
c[3].metric("變異數同質", "✅ 是" if lv["同質(p≥α)"] else "⚠️ 否")
if not lv["同質(p≥α)"]:
    st.warning("⚠️ 變異數不同質 → 依講義：前後測都改跑 t 檢定處理。")
state.register_export_table("ANCOVA_3_Levene", pd.DataFrame([lv]))

# ④ 斜率同質
st.subheader("④ 組內迴歸係數同質性檢定（組別 × 前測 交乘項，放最後；型 III）")
st.caption("交乘項 p ≥ α 代表各組斜率一致，符合 ANCOVA 前提（Reviewer 常問：IV 對共變量是否有顯著影響）。")
st.dataframe(res.slope_homogeneity, width="stretch", hide_index=True)
if res.slope_ok:
    st.success("✅ 組內迴歸係數同質，適合使用 ANCOVA。")
else:
    st.error("❌ 組內迴歸係數不同質 → 依講義：改用詹森-內曼法（Johnson-Neyman）。")
state.register_export_table("ANCOVA_4_斜率同質性", res.slope_homogeneity)

# ⑤ 主分析 ANCOVA 型III
st.subheader("⑤ 主分析：ANCOVA 主旨間效果檢定（完全因子設計、型 III 平方和）")
st.dataframe(res.ancova_table, width="stretch", hide_index=True)
st.caption(f"R² = {res.r_squared}（調整後 R² = {res.r_squared_adj}）")
if res.group_p < alpha:
    st.success(f"✅ 控制前測後，組別主效果顯著：F = {res.group_F}, p = {res.group_p} < {alpha}，"
               f"局部 η² = {res.group_eta2}（{res.eta2_magnitude}）。")
else:
    st.info(f"ℹ️ 控制前測後，組別主效果未達顯著：F = {res.group_F}, p = {res.group_p}。")
state.register_export_table("ANCOVA_5_主旨間效果檢定", res.ancova_table)

# ⑥ 調整後平均數
st.subheader("⑥ 調整後平均數（EMMeans）")
st.caption(res.adjusted_means.attrs.get("說明", "") + "　※ ANCOVA 一定要報告調整後平均數與標準誤。")
st.dataframe(res.adjusted_means, width="stretch", hide_index=True)
state.register_export_table("ANCOVA_6_調整後平均", res.adjusted_means)

# ⑦ APA 彙整表
st.subheader("⑦ APA 彙整表（可直接放進論文）")
st.caption("欄位＝Group｜N｜Mean｜SD｜Adjusted Mean｜Adjusted SD｜F｜η²（依講義慣例，Adjusted SD 欄填調整後標準誤 SE）。* p < .05")
st.dataframe(res.summary_apa, width="stretch", hide_index=True)
state.register_export_table("ANCOVA_7_APA彙整表", res.summary_apa)

# ══════════════════════════ 補充區 ══════════════════════════
st.header("▍補充區（加值，非講義必列）")

with st.expander("效果量 η² 判準（Cohen, 1988）"):
    st.markdown("- .01 ≤ η² < .059：**小效果**\n- .059 ≤ η² < .138：**中效果**\n- η² ≥ .138：**大效果**")

with st.expander("事後兩兩比較（LSD，無校正；對照講義選項的信賴區間調整＝LSD）"):
    st.dataframe(res.posthoc, width="stretch", hide_index=True)
    state.register_export_table("ANCOVA_補_事後LSD", res.posthoc)

with st.expander("📝 文章寫法（可直接改寫進論文）", expanded=True):
    st.markdown(f"**中文**：{res.article_zh}")
    st.markdown(f"**English**：{res.article_en}")
    article_tbl = pd.DataFrame(
        [{"語言": "中文", "內容": res.article_zh}, {"語言": "English", "內容": res.article_en}]
    )
    state.register_export_table("ANCOVA_補_文章寫法", article_tbl)

if res.decisions:
    st.subheader("⚠️ 假設違反的處理建議（依講義 p48）")
    for d in res.decisions:
        st.warning(d)

if res.warnings:
    st.caption("其他提醒：" + "；".join(res.warnings))

st.caption("以上結果已加入匯出清單，可回「首頁 → 匯出」一併下載。")
