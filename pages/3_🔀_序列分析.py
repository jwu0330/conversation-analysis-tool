"""Bloom 提問序列分析頁（重構版）。

三大區塊（把原本 7 個雜亂分頁收斂）：
    ① 個人序列        每位學生的 Bloom 提問時間序列
    ② 轉移分析        轉移表 → 轉移圖 → GSEQ 顯著轉移（預設只顯示「顯著偏多」）
    ③ 趨勢分析        題序流動平均 + 題序×Bloom 線性迴歸／個別學生斜率

GSEQ 修正：滯後序列分析主要解讀「顯著偏多」（正殘差＝真實模式）；「顯著偏少」
一般不下結論，預設收起。期望次數 < 5 的格子標為「可信度低」，避免誤讀。
"""
from __future__ import annotations

import streamlit as st

from src import state
from src.sequence import analysis as seq
from src.sequence import charts as seq_charts

st.set_page_config(page_title="序列分析", page_icon="🔀", layout="wide")
st.title("🔀 Bloom 提問序列分析")
st.caption("把每位學生依時間排列的 Bloom 提問層級轉成序列，觀察轉移模式並比較各組。")

df = state.require_data()

# ── 欄位對應 + 參數（共用設定列）─────────────────────────
with st.expander("① 欄位對應與分析參數", expanded=True):
    cols = list(df.columns)
    guess = seq.guess_columns(cols)

    def _idx(name: str | None) -> int:
        return cols.index(name) if name in cols else 0

    c1, c2, c3, c4 = st.columns(4)
    student_col = c1.selectbox("學生 ID 欄位", cols, index=_idx(guess["student"]))
    group_col = c2.selectbox("組別欄位", cols, index=_idx(guess["group"]))
    bloom_col = c3.selectbox("Bloom 層級欄位", cols, index=_idx(guess["bloom"]))
    order_col = c4.selectbox("排序依據（題序/時間）", cols, index=_idx(guess["order"]))

    p1, p2, p3 = st.columns(3)
    include_l0 = p1.checkbox("包含 L0", value=True)
    high_min = p2.number_input("高階起始 Level（含以上）", 1, 6, 4)
    min_edge = p3.number_input("轉移圖最小次數門檻", 0, 50, 1)

work = seq.prepare(df, student_col, group_col, bloom_col, order_col, include_l0=include_l0)
if work.empty:
    st.error("整理後沒有可用資料，請確認欄位對應（Bloom 欄需能解析數字，如 'Level 4'）。")
    st.stop()
if student_col == order_col:
    st.warning("『學生 ID』與『排序依據』選到同一欄，序列可能不正確，建議分開選。")

levels = seq.all_levels(work)
groups = sorted(work[seq.GROUP].unique().tolist())
st.caption(
    f"有效提問 {len(work)} 筆、學生 {work[seq.STUDENT].nunique()} 位、"
    f"組別 {groups}、Level：{['L' + str(v) for v in levels]}"
)

trans = seq.transitions(work)
trans_shown = trans[trans["次數"] >= min_edge]

tab_seq, tab_trans, tab_trend = st.tabs(["① 個人序列", "② 轉移分析", "③ 趨勢分析"])

# ══ ① 個人序列 ═══════════════════════════════════════════
with tab_seq:
    seqs = seq.build_sequences(work)
    st.dataframe(seqs[["學生", "組別", "提問數", "序列字串"]],
                 width="stretch", hide_index=True)
    state.register_export_table("序列_個人Bloom序列", seqs[["學生", "組別", "提問數", "序列字串"]])

# ══ ② 轉移分析（每塊可收合，圖固定小尺寸，方便單頁截圖）════
with tab_trans:
    # 共用控制列（一行放完，省版面）
    cc1, cc2, cc3 = st.columns([1, 1, 1.4])
    normalize = cc1.radio("矩陣數值", ["次數", "列機率(%)"], horizontal=True) == "列機率(%)"
    alpha = cc2.selectbox("GSEQ 顯著水準 α", [0.05, 0.01, 0.10], index=0)
    show_less = cc3.checkbox("GSEQ 也顯示「顯著偏少(↓)」（不建議下結論）", value=False)
    st.caption(
        "每組獨立收合；組內用小分頁切換四種視角，圖為固定小尺寸，方便單頁截圖。"
        "GSEQ 調整殘差 z：|z|>1.96 為顯著偏多(↑)＝真實模式；偏少(↓)一般不下結論；期望<5 標『可信度低』。"
    )

    gseq_all = seq.gseq_all_groups(trans, groups, levels, alpha=alpha)
    wanted = ["↑ 顯著偏多"] + (["↓ 顯著偏少"] if show_less else [])

    # 轉移表（收合）
    with st.expander("📋 轉移表（Source→Target 次數，全部組別）", expanded=False):
        st.dataframe(trans, width="stretch", hide_index=True)
        state.register_export_table("序列_Bloom轉移表", trans)

    # 每組一個收合區，組內用小分頁切換視角
    for grp in groups:
        g_trans = trans_shown[trans_shown["組別"] == grp]
        with st.expander(f"🔹 {grp}：轉移圖與 GSEQ", expanded=False):
            v_sankey, v_net, v_heat, v_gseq = st.tabs(
                ["Sankey 流向", "圈箭頭圖", "矩陣熱圖", "GSEQ 顯著轉移"]
            )
            with v_sankey:
                st.plotly_chart(
                    seq_charts.transition_sankey(g_trans, title=f"{grp}：Bloom 轉移流向"),
                    width="stretch",
                )
            with v_net:
                st.caption("Level 釘成六邊形；綠=往高階、橘=往低階、灰=同層。")
                st.graphviz_chart(
                    seq_charts.transition_graph(g_trans, levels, high_min=int(high_min)),
                    width="content",
                )
            with v_heat:
                matrix = seq.transition_matrix(trans, grp, levels, normalize=normalize)
                st.plotly_chart(
                    seq_charts.transition_heatmap(matrix, title=f"{grp}：轉移矩陣"),
                    width="stretch",
                )
                state.register_export_table(
                    f"序列_轉移矩陣_{grp}",
                    seq.transition_matrix(trans, grp, levels, normalize=normalize),
                )
            with v_gseq:
                gdf = gseq_all[gseq_all["組別"] == grp].copy()
                gdf_graph = gdf.copy()
                if not show_less:  # 沒勾偏少就把偏少當未顯著（圖只留顯著偏多）
                    gdf_graph.loc[gdf_graph["顯著"] == "↓ 顯著偏少", "顯著"] = ""
                st.graphviz_chart(
                    seq_charts.gseq_graph(gdf_graph, levels, high_min=int(high_min),
                                          only_significant=True),
                    width="content",
                )
                shown = gdf[gdf["顯著"].isin(wanted)].sort_values("調整殘差z", ascending=False)
                if shown.empty:
                    st.info("（此組沒有達顯著偏多的轉移）")
                else:
                    st.dataframe(shown, width="stretch", hide_index=True)
                state.register_export_table(f"序列_GSEQ統計_{grp}", gdf)

    # 高低階轉移（收合）
    with st.expander("📊 高低階轉移（低→高／高→高／高→低／低→低）", expanded=False):
        highlow = seq.high_low_transitions(work, high_min=int(high_min))
        st.dataframe(highlow, width="stretch", hide_index=True)
        st.plotly_chart(
            seq_charts.highlow_bar(highlow, title="高低階轉移（組內比例）"), width="stretch"
        )
        state.register_export_table("序列_高低階轉移", highlow)

# ══ ③ 趨勢分析（題序流動 + 迴歸軌跡）══════════════════════
with tab_trend:
    st.markdown("#### 題序流動：各組每一題的平均 Bloom Level")
    profile = seq.position_profile(work)
    st.plotly_chart(
        seq_charts.position_line(profile, title="題序流動：各組平均 Bloom Level"),
        width="stretch",
    )
    st.dataframe(profile, width="stretch", hide_index=True)
    state.register_export_table("序列_題序剖面", profile)

    st.divider()
    st.markdown("#### 趨勢／軌跡：題序 × Bloom 線性迴歸")
    o1, o2 = st.columns(2)
    show_zones = o1.checkbox("顯示高低階底色", value=True)
    show_band = o2.checkbox("顯示 95% 信賴區帶", value=True)

    points = seq.position_points(work)
    bands = {g: seq.regression_band(work, g) for g in groups}
    st.plotly_chart(
        seq_charts.trend_figure(
            points, bands, high_min=int(high_min),
            level_min=min(levels), level_max=max(levels),
            show_band=show_band, show_zones=show_zones,
            title="題序 × Bloom Level 趨勢",
        ),
        width="stretch",
    )

    regs = seq.regression_by_group(work)
    st.markdown("**各組迴歸結果**（斜率＝每多問一題，Bloom 平均變化）")
    st.dataframe(regs, width="stretch", hide_index=True)
    for _, r in regs.iterrows():
        if r["斜率"] is None:
            continue
        trend = "逐步深化 ↗" if r["斜率"] > 0 else "逐步下降 ↘" if r["斜率"] < 0 else "持平"
        sig = "（顯著）" if r["顯著"] == "是" else "（未達顯著）"
        st.write(f"- **{r['組別']}**：斜率 {r['斜率']:+.3f}／題，R²={r['R²']}，p={r['p值']} {sig} → {trend}")
    state.register_export_table("序列_趨勢迴歸", regs)

    slopes = seq.student_slopes(work)
    st.markdown("**個別學生迴歸斜率分布**（每點一位學生）")
    st.plotly_chart(
        seq_charts.student_slope_box(slopes, title="各組學生迴歸斜率比較"), width="stretch"
    )
    if not slopes.empty:
        summary = (
            slopes.groupby("組別")["斜率"]
            .agg(人數="count", 平均斜率="mean", 正斜率人數=lambda s: int((s > 0).sum()))
            .reset_index()
        )
        summary["平均斜率"] = summary["平均斜率"].round(4)
        summary["正斜率比例(%)"] = (summary["正斜率人數"] / summary["人數"] * 100).round(1)
        st.dataframe(summary, width="stretch", hide_index=True)
        state.register_export_table("序列_學生斜率", slopes)

st.success("序列分析結果已加入匯出清單，可回「首頁 → 匯出」一併下載。")
