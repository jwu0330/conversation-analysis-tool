"""敘述性統計頁：描述統計 / 次數累積排名 / 相關分析 / t 檢定 / 交叉熱力圖。

把原本散在多頁的「描述性」內容整併到同一頁，用分頁按鈕排列，一目了然。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import state
from src.core import charts, column_types, descriptive, grouping, stat_tests

st.set_page_config(page_title="敘述性統計", page_icon="📈", layout="wide")
st.title("📈 敘述性統計")
st.caption("描述統計、次數／累積排名、相關分析、兩組 t 檢定、多組 ANOVA、交叉熱力圖。")

df = state.require_data()
num_cols = column_types.numeric_columns(df)
cat_cols = column_types.categorical_columns(df)

tab_desc, tab_freq, tab_corr, tab_ttest, tab_anova, tab_cross = st.tabs(
    ["描述統計", "次數／累積排名", "相關分析", "兩組 t 檢定", "多組 ANOVA", "交叉熱力圖"]
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

# ── 兩組 t 檢定 ───────────────────────────────────────────
with tab_ttest:
    st.caption("比較兩組在某數值欄位的平均數；自動判斷等變異 / Welch，附 Cohen's d。")
    if not num_cols or not cat_cols:
        st.info("需要至少一個數值欄位與一個類別（2 組）欄位。")
    else:
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            value_col = st.selectbox("數值欄位", options=num_cols)
        with c2:
            group_col = st.selectbox("分組欄位（2 組）", options=cat_cols)
        with c3:
            alpha = st.selectbox("α", [0.05, 0.01, 0.10], index=0, key="tt_alpha")
        if st.button("執行 t 檢定", type="primary"):
            r = stat_tests.independent_t_test(df, value_col, group_col, alpha=alpha)
            if r.significant:
                st.success(f"✅ t = {r.statistic:.3f}，p = {r.p_value:.4f} < {alpha}，達顯著。")
            elif r.p_value == r.p_value:
                st.info(f"ℹ️ t = {r.statistic:.3f}，p = {r.p_value:.4f} ≥ {alpha}，未達顯著。")
            st.markdown(f"**方法**：{r.method}")
            st.markdown(f"**解釋**：{r.interpretation}")
            if r.warnings:
                st.warning("\n".join(f"- {w}" for w in r.warnings))
            summary = pd.DataFrame(
                [{"項目": k, "內容": v} for k, v in r.extra.items()]
            )
            state.register_export_table(f"t檢定_{value_col}_by_{group_col}", summary)

# ── 多組 ANOVA（≥3 組；含「問題數量」計數模式）────────────
with tab_anova:
    st.caption(
        "比較 **3 組以上** 平均數（t 檢定只能 2 組）。"
        "要看「各知識點的**問題數量**有沒有顯著差異」就用下方**計數模式**。"
    )
    mode = st.radio("分析對象", ["問題數量（計數）", "用現有數值欄"], horizontal=True)
    a_alpha = st.selectbox("α", [0.05, 0.01, 0.10], index=0, key="anova_alpha")

    if mode == "用現有數值欄":
        if not num_cols or not cat_cols:
            st.info("需要一個數值欄位與一個分類欄位。")
        else:
            c1, c2 = st.columns(2)
            dv = c1.selectbox("數值欄位（依變數）", num_cols, key="anova_dv")
            fac = c2.selectbox("分類欄位（因子，≥3 組佳）", cat_cols, key="anova_fac")
            run_df, run_dv, run_fac = df, dv, fac
    else:
        st.caption("計數＝每個「觀察單位×分類」的提問筆數；未出現的組合補 0（例：某生沒問到某知識點＝0）。")
        c1, c2, c3 = st.columns(3)
        unit = c1.selectbox("觀察單位", cat_cols,
                            index=(cat_cols.index("學生") if "學生" in cat_cols else 0), key="anova_unit")
        cat = c2.selectbox("分類欄（因子，例：知識點）", [c for c in cat_cols if c != unit],
                           index=0, key="anova_cat")
        c3.caption("未出現的組合依計數定義補 0")
        counts = df.groupby([unit, cat]).size().unstack(fill_value=0).stack().reset_index(name="問題數量")
        run_df, run_dv, run_fac = counts, "問題數量", cat
        with st.expander(f"計數表（{run_df.shape[0]} 列：{unit} × {cat}）"):
            st.dataframe(run_df, width="stretch", hide_index=True)

    if st.button("執行 ANOVA", type="primary"):
        r = (stat_tests.one_way_anova(run_df, run_dv, run_fac, alpha=a_alpha)
             if mode == "用現有數值欄"
             else stat_tests.friedman_count_test(df, unit, cat, alpha=a_alpha))
        if r.p_value != r.p_value:
            st.error(r.interpretation)
            for w in r.warnings:
                st.warning(w)
        else:
            if r.significant:
                symbol = "F" if mode == "用現有數值欄" else "χ²"
                st.success(f"✅ {symbol} = {r.statistic:.3f}，p = {r.p_value:.4f} < {a_alpha}，"
                           f"達顯著。")
            else:
                symbol = "F" if mode == "用現有數值欄" else "χ²"
                st.info(f"ℹ️ {symbol} = {r.statistic:.3f}，p = {r.p_value:.4f} ≥ {a_alpha}，未達顯著。")
            st.markdown(f"**解釋**：{r.interpretation}")

            if mode == "用現有數值欄":
                st.markdown("**各組描述統計**")
                st.dataframe(r.extra["描述統計"], width="stretch", hide_index=True)
                st.markdown("**ANOVA 摘要表**")
                st.dataframe(r.extra["ANOVA表"], width="stretch", hide_index=True)
                lc = st.columns(3)
                lc[0].metric("Levene F", r.extra["Levene_F"])
                lc[1].metric("Levene p", r.extra["Levene_p"])
                lc[2].metric("採用方法", r.extra["採用方法"])
            if r.extra.get("Tukey事後") is not None:
                st.markdown(f"**{r.extra['採用方法'].split(' + ')[-1]} 事後兩兩比較**")
                st.dataframe(r.extra["Tukey事後"], width="stretch", hide_index=True)
            if r.warnings:
                st.warning("\n".join(f"- {w}" for w in r.warnings))
            state.register_export_table(f"ANOVA_{run_dv}_by_{run_fac}", r.extra["ANOVA表"])
            state.register_export_table(f"ANOVA描述_{run_dv}_by_{run_fac}", r.extra["描述統計"])


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
