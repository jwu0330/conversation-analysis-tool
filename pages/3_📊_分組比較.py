"""分組比較頁：分組欄位 × 比較欄位 → 交叉表、百分比表、長條圖/堆疊圖/熱圖。"""
from __future__ import annotations

import streamlit as st

from src import state
from src.core import charts, column_types, grouping

st.set_page_config(page_title="分組比較", page_icon="📊", layout="wide")
st.title("📊 分組比較")

df = state.require_data()

cat_cols = column_types.categorical_columns(df)
num_cols = column_types.numeric_columns(df)
all_cols = list(df.columns)

if len(all_cols) < 2:
    st.warning("欄位不足，至少需要 2 個欄位才能做分組比較。")
    st.stop()

c1, c2 = st.columns(2)
with c1:
    group_col = st.selectbox(
        "分組欄位（例如：組別、班級、時間點）",
        options=all_cols,
        index=all_cols.index(cat_cols[0]) if cat_cols else 0,
    )
with c2:
    remaining = [c for c in all_cols if c != group_col]
    compare_col = st.selectbox("比較欄位（例如：Bloom 層級、知識點）", options=remaining)

mode = st.radio(
    "分析方式",
    ["類別交叉（次數/百分比）", "數值聚合（平均/標準差等）"],
    horizontal=True,
)

st.divider()

if mode == "類別交叉（次數/百分比）":
    norm_label = st.radio(
        "數值呈現",
        ["次數", "列百分比(%)", "欄百分比(%)", "總百分比(%)"],
        horizontal=True,
    )
    norm_map = {
        "次數": False,
        "列百分比(%)": "index",
        "欄百分比(%)": "columns",
        "總百分比(%)": "all",
    }
    ct = grouping.crosstab(df, group_col, compare_col, normalize=norm_map[norm_label])
    st.subheader("交叉表")
    st.dataframe(ct, width="stretch")
    state.register_export_table(f"交叉表_{group_col}x{compare_col}", ct)

    # 長格式供繪圖
    as_pct = norm_label != "次數"
    long_df = grouping.group_frequency(df, group_col, compare_col, as_percentage=as_pct)
    y_col = "百分比(%)" if as_pct else "次數"

    st.subheader("圖表")
    tab1, tab2, tab3 = st.tabs(["群組長條圖", "堆疊長條圖", "熱圖"])
    with tab1:
        fig = charts.bar_chart(
            long_df, x=group_col, y=y_col, color=compare_col,
            title=f"{group_col} × {compare_col}",
        )
        st.plotly_chart(fig, width="stretch")
    with tab2:
        fig = charts.stacked_bar_chart(
            long_df, x=group_col, y=y_col, color=compare_col,
            title=f"{group_col} × {compare_col}（堆疊）",
        )
        st.plotly_chart(fig, width="stretch")
    with tab3:
        matrix = grouping.crosstab(
            df, group_col, compare_col, normalize=False, margins=False
        )
        fig = charts.heatmap(matrix, title=f"{group_col} × {compare_col} 次數熱圖")
        st.plotly_chart(fig, width="stretch")

else:  # 數值聚合
    if not num_cols:
        st.warning("資料中沒有數值欄位，無法做數值聚合。請改用「類別交叉」。")
        st.stop()
    value_col = st.selectbox("要聚合的數值欄位（例如：分數）", options=num_cols)
    aggs = st.multiselect(
        "聚合方式",
        options=list(grouping.GROUP_AGGS.keys()),
        default=["count", "mean", "std"],
        format_func=lambda k: f"{grouping.GROUP_AGGS[k]} ({k})",
    )
    if not aggs:
        st.info("請至少選擇一種聚合方式。")
        st.stop()
    result = grouping.group_aggregate(df, [group_col], value_col, aggs)
    st.subheader("分組統計表")
    st.dataframe(result, width="stretch", hide_index=True)
    state.register_export_table(f"分組統計_{group_col}_{value_col}", result)

    if "平均" in result.columns:
        fig = charts.bar_chart(
            result, x=group_col, y="平均", title=f"各{group_col}的{value_col}平均"
        )
        st.plotly_chart(fig, width="stretch")
