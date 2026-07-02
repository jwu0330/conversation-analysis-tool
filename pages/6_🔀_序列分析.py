"""Bloom 提問序列分析頁（前端入口共用，後端邏輯在 src/sequence，獨立於 core）。

依 SPEC：個人序列 → Lag-1 轉移表 → 轉移圖(Sankey)/矩陣熱圖
→ 高低階轉移 → 題序流動圖。
"""
from __future__ import annotations

import streamlit as st

from src import state
from src.sequence import analysis as seq
from src.sequence import charts as seq_charts

st.set_page_config(page_title="序列分析", page_icon="🔀", layout="wide")
st.title("🔀 Bloom 提問序列分析")

st.markdown(
    "把每位學生依時間排列的 Bloom 提問層級轉成序列，觀察**提問歷程的轉移模式**"
    "（低階→高階、能否維持高階），並比較實驗組與對照組。"
    "此模組後端獨立，不影響前面的描述統計/檢定。"
)

df = state.require_data()

# --- 欄位對應（自動猜測，可手動調整）---
st.subheader("① 欄位對應")
cols = list(df.columns)
guess = seq.guess_columns(cols)


def _idx(name: str | None) -> int:
    return cols.index(name) if name in cols else 0


c1, c2, c3, c4 = st.columns(4)
with c1:
    student_col = st.selectbox("學生 ID 欄位", cols, index=_idx(guess["student"]))
with c2:
    group_col = st.selectbox("組別欄位", cols, index=_idx(guess["group"]))
with c3:
    bloom_col = st.selectbox("Bloom 層級欄位", cols, index=_idx(guess["bloom"]))
with c4:
    order_col = st.selectbox("排序依據（題序/時間）", cols, index=_idx(guess["order"]))

# --- 參數 ---
st.subheader("② 分析參數")
p1, p2, p3 = st.columns(3)
with p1:
    include_l0 = st.checkbox("包含 L0", value=True, help="可切換含 L0 與排除 L0 兩版")
with p2:
    high_min = st.number_input("高階起始 Level（含以上為高階）", 1, 6, 4)
with p3:
    min_edge = st.number_input("轉移圖最小次數門檻", 0, 50, 1, help="低於此次數的轉移不畫，避免圖太雜")

# --- 整理資料 ---
work = seq.prepare(df, student_col, group_col, bloom_col, order_col, include_l0=include_l0)
if work.empty:
    st.error("整理後沒有可用資料，請確認欄位對應（Bloom 欄位需能解析出數字，如 'Level 4'）。")
    st.stop()
if student_col == order_col:
    st.warning("『學生 ID』與『排序依據』選到同一欄，序列可能不正確，建議分開選。")

levels = seq.all_levels(work)
groups = sorted(work[seq.GROUP].unique().tolist())
st.caption(
    f"有效提問 {len(work)} 筆、學生 {work[seq.STUDENT].nunique()} 位、"
    f"組別 {groups}、出現的 Level：{['L'+str(v) for v in levels]}"
)

trans = seq.transitions(work)
trans_shown = trans[trans["次數"] >= min_edge]

tab_seq, tab_table, tab_diagram, tab_highlow, tab_flow = st.tabs(
    ["個人序列", "轉移表", "轉移圖", "高低階轉移", "題序流動圖"]
)

# ① 個人序列
with tab_seq:
    seqs = seq.build_sequences(work)
    st.dataframe(
        seqs[["學生", "組別", "提問數", "序列字串"]], width="stretch", hide_index=True
    )
    state.register_export_table("序列_個人Bloom序列", seqs[["學生", "組別", "提問數", "序列字串"]])

# ② 轉移表
with tab_table:
    st.caption("Source＝前一題 Bloom Level，Target＝下一題，次數＝該轉移出現次數。")
    st.dataframe(trans, width="stretch", hide_index=True)
    state.register_export_table("序列_Bloom轉移表", trans)

# ③ 轉移圖（圈圈箭頭網絡圖 + Sankey + 矩陣熱圖）
with tab_diagram:
    st.caption(
        "🔵 圓圈＝Bloom Level，箭頭＝前題轉到後題（含 L2→L2 自我迴圈），"
        "箭頭越粗＝次數越多。顏色：綠＝往高階、橘＝往低階、灰＝同層級。"
    )
    normalize = st.radio(
        "矩陣數值", ["次數", "列機率(%)"], horizontal=True,
        help="列機率＝前題為某 Level 時，接續各 Level 的百分比",
    ) == "列機率(%)"
    for grp in groups:
        st.markdown(f"#### {grp}")
        g_trans = trans_shown[trans_shown["組別"] == grp]

        # 圈圈箭頭轉移網絡圖（使用者指定的圖）
        st.graphviz_chart(
            seq_charts.transition_dot(g_trans, high_min=int(high_min)),
            width="stretch",
        )

        with st.expander(f"{grp}：Sankey 流向圖與轉移矩陣"):
            colA, colB = st.columns(2)
            with colA:
                st.plotly_chart(
                    seq_charts.transition_sankey(g_trans, title=f"{grp}：Bloom 轉移路徑"),
                    width="stretch",
                )
            with colB:
                matrix = seq.transition_matrix(trans, grp, levels, normalize=normalize)
                st.plotly_chart(
                    seq_charts.transition_heatmap(matrix, title=f"{grp}：轉移矩陣"),
                    width="stretch",
                )
        matrix = seq.transition_matrix(trans, grp, levels, normalize=normalize)
        state.register_export_table(f"序列_轉移矩陣_{grp}", matrix)

# ④ 高低階轉移
with tab_highlow:
    st.caption(f"L{high_min} 以上為高階、其餘為低階，觀察四種轉移。")
    highlow = seq.high_low_transitions(work, high_min=int(high_min))
    st.dataframe(highlow, width="stretch", hide_index=True)
    st.plotly_chart(
        seq_charts.highlow_bar(highlow, title="高低階轉移（組內比例）"),
        width="stretch",
    )
    state.register_export_table("序列_高低階轉移", highlow)

# ⑤ 題序流動圖
with tab_flow:
    st.caption("各組在第 1、2、3… 題的平均 Bloom Level，觀察是否逐步深化。")
    profile = seq.position_profile(work)
    st.plotly_chart(
        seq_charts.position_line(profile, title="題序流動：各組平均 Bloom Level"),
        width="stretch",
    )
    st.dataframe(profile, width="stretch", hide_index=True)
    state.register_export_table("序列_題序剖面", profile)

st.success("序列分析結果已加入匯出清單，可到「📥 匯出」頁一併下載。")
