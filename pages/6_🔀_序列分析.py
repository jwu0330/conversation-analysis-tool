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

with st.expander("📐 計算方式與公式（摘要）"):
    st.markdown(
        "**步驟**：每位學生依排序欄位排出 Bloom 序列 → 取相鄰兩題 (Lag-1) 統計"
        "「前題 i → 後題 j」的轉移次數 O。\n\n"
        "**GSEQ 式指標**（$R_i$＝列和、$C_j$＝欄和、$N$＝總轉移數）："
    )
    st.latex(r"E_{ij}=\frac{R_i\,C_j}{N}\quad\ "
             r"P_{ij}=\frac{O_{ij}}{R_i}\quad\ "
             r"z_{ij}=\frac{O_{ij}-E_{ij}}{\sqrt{E_{ij}\,(1-R_i/N)(1-C_j/N)}}")
    st.markdown(
        "期望次數 $E$、轉移機率 $P$、調整後殘差 $z$；$|z|>1.96$ 即該轉移顯著偏多(↑)/偏少(↓)。"
        "完整推導與參考文獻見 `docs/序列分析方法.md`。"
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

tab_seq, tab_table, tab_diagram, tab_gseq, tab_highlow, tab_flow, tab_trend = st.tabs(
    ["個人序列", "轉移表", "轉移圖", "GSEQ 顯著轉移", "高低階轉移", "題序流動圖", "趨勢/軌跡"]
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
        "圓圈＝Bloom Level（🔵藍＝低階、🔴紅＝高階），位置固定成六邊形。"
        "箭頭：🟢綠＝往較高階、🟠橘＝往較低階、⚪灰＝停在同層（自我迴圈）；"
        "箭頭越粗、數字越大＝該轉移次數越多。"
    )
    normalize = st.radio(
        "矩陣數值", ["次數", "列機率(%)"], horizontal=True,
        help="列機率＝前題為某 Level 時，接續各 Level 的百分比",
    ) == "列機率(%)"
    for grp in groups:
        st.markdown(f"#### {grp}")
        g_trans = trans_shown[trans_shown["組別"] == grp]

        # 圈圈箭頭轉移網絡圖（六邊形固定位置）
        st.graphviz_chart(
            seq_charts.transition_graph(g_trans, levels, high_min=int(high_min)),
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

# ③-2 GSEQ 顯著轉移
with tab_gseq:
    st.caption(
        "GSEQ 式滯後序列分析：比對每個轉移的『觀察 vs 期望』次數，"
        "算出**調整殘差 z**——|z|>1.96 表示該轉移顯著多於（↑）或少於（↓）隨機預期。"
        "這回答的是『哪些轉移是真正的模式，而非因某層級本來就常見』。詳見 docs/序列分析方法.md。"
    )
    alpha = st.selectbox("顯著水準 α", [0.05, 0.01, 0.10], index=0)
    only_sig = st.checkbox("只顯示達顯著的轉移", value=True)
    gseq_all = seq.gseq_all_groups(trans, groups, levels, alpha=alpha)
    for grp in groups:
        st.markdown(f"#### {grp}")
        gdf = gseq_all[gseq_all["組別"] == grp]
        shown = gdf[gdf["顯著"] != ""] if only_sig else gdf
        shown = shown.sort_values("調整殘差z", ascending=False)
        if shown.empty:
            st.info("（此組沒有達顯著的轉移）")
        else:
            st.dataframe(shown, width="stretch", hide_index=True)
        state.register_export_table(f"序列_GSEQ統計_{grp}", gdf)
    st.caption(
        "註：期望次數過低（<5）時 z 的常態近似會變差，需謹慎解讀；"
        "本工具目前為 Lag-1，如需多重 Lag 可再匯出資料轉入正式 GSEQ。"
    )

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

# ⑥ 趨勢/軌跡（題序 × Bloom 的散布 + 線性迴歸 + 個別學生斜率）
with tab_trend:
    st.caption(
        "X＝題序（時間）、Y＝Bloom Level。散布點＝每一題提問；每組配一條**線性迴歸線**"
        "（斜率＞0 且顯著＝提問隨時間逐步深化），陰影為 95% 信賴區帶，"
        "底色區分高/低階。下方箱型圖比較**每位學生自己的迴歸斜率**，看多數人趨勢往哪走。"
    )
    o1, o2 = st.columns(2)
    with o1:
        show_zones = st.checkbox("顯示高低階底色", value=True)
    with o2:
        show_band = st.checkbox("顯示 95% 信賴區帶", value=True)

    points = seq.position_points(work)
    regs = seq.regression_by_group(work)
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

    st.markdown("**各組迴歸結果**（斜率＝每多問一題，Bloom 平均變化）")
    st.dataframe(regs, width="stretch", hide_index=True)
    for _, r in regs.iterrows():
        if r["斜率"] is None:
            continue
        trend = "逐步深化 ↗" if r["斜率"] > 0 else "逐步下降 ↘" if r["斜率"] < 0 else "持平"
        sig = "（顯著）" if r["顯著"] == "是" else "（未達顯著）"
        st.write(
            f"- **{r['組別']}**：斜率 {r['斜率']:+.3f}／題，R²={r['R²']}，"
            f"p={r['p值']} {sig} → {trend}"
        )
    state.register_export_table("序列_趨勢迴歸", regs)

    slopes = seq.student_slopes(work)
    st.markdown("**個別學生迴歸斜率分布**（每點一位學生；斜率＞0＝該生提問逐步深化）")
    st.plotly_chart(
        seq_charts.student_slope_box(slopes, title="各組學生迴歸斜率比較"),
        width="stretch",
    )
    if not slopes.empty:
        summary = (
            slopes.groupby("組別")["斜率"]
            .agg(人數="count", 平均斜率="mean", 正斜率人數=lambda s: int((s > 0).sum()))
            .reset_index()
        )
        summary["平均斜率"] = summary["平均斜率"].round(4)
        summary["正斜率比例(%)"] = (
            summary["正斜率人數"] / summary["人數"] * 100
        ).round(1)
        st.dataframe(summary, width="stretch", hide_index=True)
        state.register_export_table("序列_學生斜率", slopes)

st.success("序列分析結果已加入匯出清單，可到「📥 匯出」頁一併下載。")
