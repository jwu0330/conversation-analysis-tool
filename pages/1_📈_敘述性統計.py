"""敘述性統計頁：描述統計 / 次數累積排名 / 相關分析 / 交叉熱力圖。

把原本散在多頁的「描述性」內容整併到同一頁，用分頁按鈕排列，一目了然。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import state
from src.core import charts, column_types, descriptive, grouping

st.set_page_config(page_title="敘述性統計", page_icon="📈", layout="wide")
st.title("📈 敘述性統計")
st.caption("描述統計、次數／累積排名、相關分析與交叉熱力圖。t 檢定、ANOVA 等推論方法請到「統計分析」。")

df = state.require_data()
num_cols = column_types.numeric_columns(df)
cat_cols = column_types.categorical_columns(df)

tab_desc, tab_freq, tab_corr, tab_cross = st.tabs(
    ["描述統計", "次數／累積排名", "相關分析", "交叉熱力圖"]
)

# ── 描述統計 ──────────────────────────────────────────────
with tab_desc:
    col = st.selectbox("選擇欄位", options=list(df.columns), key="desc_col")
    col_type = column_types.infer_column_type(df[col])
    is_numeric = col_type == column_types.NUMERIC
    st.caption(f"型態辨識：**{column_types.TYPE_LABELS_ZH[col_type]}**")
    default_funcs = (
        ["count", "mean", "median", "std", "min", "max"]
        if is_numeric else ["count", "unique", "missing"]
    )
    chosen = st.multiselect(
        "統計函數（含中位數）",
        options=list(descriptive.NUMERIC_STATS.keys()),
        default=default_funcs,
        format_func=lambda k: f"{descriptive.NUMERIC_STATS[k][0]} ({k})",
    )
    if chosen:
        result = descriptive.describe_numeric(df[col], chosen)
        st.dataframe(result, width="stretch", hide_index=True)
        state.register_export_table(f"描述統計_{col}", result)

# ── 次數／累積排名 ────────────────────────────────────────
with tab_freq:
    col = st.selectbox("選擇類別欄位", options=list(df.columns), key="freq_col")
    dropna = st.checkbox("排除缺漏值", value=True)
    freq = descriptive.frequency_table(df[col], dropna=dropna)
    st.caption("欄位：次數、比例、百分比、累積百分比、排名。")
    st.dataframe(freq, width="stretch", hide_index=True)
    state.register_export_table(f"次數表_{col}", freq)
    if len(freq) <= 50:
        st.plotly_chart(
            charts.bar_chart(freq, x="類別", y="次數", title=f"{col} 次數分布"),
            width="stretch",
        )

# ── 相關分析 ──────────────────────────────────────────────
with tab_corr:
    if len(num_cols) < 2:
        st.info("需要至少 2 個數值欄位才能做相關分析。")
    else:
        c1, c2 = st.columns([3, 1])
        with c1:
            sel = st.multiselect("選擇數值欄位（≥2）", options=num_cols,
                                 default=num_cols[: min(5, len(num_cols))])
        with c2:
            method = st.selectbox("方法", ["pearson", "spearman", "kendall"])
        if len(sel) >= 2:
            corr = descriptive.correlation_matrix(df, sel, method=method)
            st.plotly_chart(
                charts.heatmap(corr, title=f"{method} 相關係數矩陣"), width="stretch"
            )
            pairs = descriptive.correlation_pairs(df, sel, method=method)
            st.markdown("**兩兩相關（含 p 值與顯著）**")
            st.dataframe(pairs, width="stretch", hide_index=True)
            state.register_export_table(f"相關矩陣_{method}", corr.reset_index())
            state.register_export_table(f"相關檢定_{method}", pairs)

# ── 交叉熱力圖 ────────────────────────────────────────────
with tab_cross:
    st.caption("兩個類別欄位的交叉次數，用熱力圖呈現分布。")
    if len(cat_cols) < 2:
        st.info("需要至少 2 個類別欄位。")
    else:
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            row = st.selectbox("列（Row）", options=cat_cols, index=0)
        with c2:
            col_b = st.selectbox("欄（Column）",
                                 options=[c for c in cat_cols if c != row])
        with c3:
            mode = st.selectbox("數值", ["次數", "列百分比", "欄百分比"])
        norm = {"次數": False, "列百分比": "index", "欄百分比": "columns"}[mode]
        ct = grouping.crosstab(df, row, col_b, normalize=norm, margins=False)
        st.plotly_chart(
            charts.heatmap(ct, title=f"{row} × {col_b}（{mode}）"), width="stretch"
        )
        st.dataframe(ct, width="stretch")
        state.register_export_table(f"交叉表_{row}x{col_b}", ct.reset_index())
