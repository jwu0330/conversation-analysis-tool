"""描述統計頁：選欄位 → 選統計函數 → 產生統計表 / 次數表。"""
from __future__ import annotations

import streamlit as st

from src import state
from src.core import column_types, descriptive

st.set_page_config(page_title="描述統計", page_icon="🧮", layout="wide")
st.title("🧮 描述統計")

df = state.require_data()

col = st.selectbox("選擇要分析的欄位", options=list(df.columns))
col_type = column_types.infer_column_type(df[col])
st.caption(f"此欄位型態辨識為：**{column_types.TYPE_LABELS_ZH[col_type]}**")

is_numeric = col_type == column_types.NUMERIC

tab_num, tab_freq = st.tabs(["數值統計", "次數／比例表"])

with tab_num:
    if not is_numeric:
        st.info("此欄位非數值型，數值統計可能不適用（僅顯示 count/unique/missing 較有意義）。")
    default_funcs = (
        ["count", "mean", "median", "std", "min", "max"]
        if is_numeric
        else ["count", "unique", "missing"]
    )
    chosen = st.multiselect(
        "選擇統計函數",
        options=list(descriptive.NUMERIC_STATS.keys()),
        default=default_funcs,
        format_func=lambda k: f"{descriptive.NUMERIC_STATS[k][0]} ({k})",
    )
    if chosen:
        result = descriptive.describe_numeric(df[col], chosen)
        st.dataframe(result, width="stretch", hide_index=True)
        state.register_export_table(f"描述統計_{col}", result)
    else:
        st.info("請至少選擇一個統計函數。")

with tab_freq:
    st.caption("各類別的次數、比例、百分比、累積百分比與排名（適用類別欄位）。")
    dropna = st.checkbox("排除缺漏值", value=True)
    freq = descriptive.frequency_table(df[col], dropna=dropna)
    st.dataframe(freq, width="stretch", hide_index=True)
    state.register_export_table(f"次數表_{col}", freq)
    if len(freq) <= 50:
        from src.core import charts

        fig = charts.bar_chart(freq, x="類別", y="次數", title=f"{col} 次數分布")
        st.plotly_chart(fig, width="stretch")
