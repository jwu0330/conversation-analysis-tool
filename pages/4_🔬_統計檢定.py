"""統計檢定頁：卡方獨立性檢定 + p 值 + Cramér's V 效果量。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import state
from src.core import charts, column_types, stat_tests

st.set_page_config(page_title="統計檢定", page_icon="🔬", layout="wide")
st.title("🔬 統計檢定")

df = state.require_data()

st.markdown(
    "目前 MVP 提供 **卡方獨立性檢定**：檢驗兩個類別欄位的分布是否有關聯。"
    "（v2 將擴充 t 檢定、ANOVA、非參數檢定與相關分析。）"
)

cat_cols = column_types.categorical_columns(df)
if len(cat_cols) < 2:
    st.warning("需要至少 2 個類別欄位才能做卡方檢定。可到「資料上傳」頁確認欄位型態。")
    # 仍允許使用者從全部欄位挑選
    cat_cols = list(df.columns)

c1, c2, c3 = st.columns([2, 2, 1])
with c1:
    col_a = st.selectbox("欄位 A（例如：組別）", options=cat_cols, index=0)
with c2:
    others = [c for c in cat_cols if c != col_a]
    col_b = st.selectbox("欄位 B（例如：Bloom 層級）", options=others)
with c3:
    alpha = st.selectbox("顯著水準 α", options=[0.05, 0.01, 0.10], index=0)

if st.button("執行卡方檢定", type="primary"):
    result = stat_tests.chi_square_test(df, col_a, col_b, alpha=alpha)

    st.subheader("檢定結果")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("卡方值", f"{result.statistic:.3f}")
    m2.metric("自由度", result.extra.get("自由度", "-"))
    m3.metric("p 值", f"{result.p_value:.4f}")
    v = result.effect_size.get("Cramér's V", float("nan"))
    m4.metric("Cramér's V", f"{v:.3f}" if v == v else "-")

    if result.significant:
        st.success(f"✅ p = {result.p_value:.4f} < {alpha}，**達統計顯著**。")
    else:
        st.info(f"ℹ️ p = {result.p_value:.4f} ≥ {alpha}，**未達統計顯著**。")

    st.markdown(f"**使用方法**：{result.method}")
    st.markdown(f"**適用條件**：{result.applicable}")
    st.markdown(f"**效果量**：Cramér's V = {v:.3f}（{result.effect_size.get('強度', '-')}）")
    st.markdown(f"**中文解釋**：{result.interpretation}")

    if result.warnings:
        st.warning("**注意事項**\n\n" + "\n".join(f"- {w}" for w in result.warnings))

    observed = result.extra.get("觀察次數表")
    expected = result.extra.get("期望次數表")
    if observed is not None:
        t1, t2, t3 = st.tabs(["觀察次數", "期望次數", "熱圖"])
        with t1:
            st.dataframe(observed, width="stretch")
        with t2:
            st.dataframe(expected, width="stretch")
        with t3:
            st.plotly_chart(
                charts.heatmap(observed, title=f"{col_a} × {col_b} 觀察次數"),
                width="stretch",
            )

    # 匯出：把檢定摘要整理成表
    summary = pd.DataFrame(
        [
            {"項目": "檢定方法", "內容": result.method},
            {"項目": "欄位 A", "內容": col_a},
            {"項目": "欄位 B", "內容": col_b},
            {"項目": "卡方值", "內容": round(result.statistic, 4)},
            {"項目": "自由度", "內容": result.extra.get("自由度")},
            {"項目": "樣本數", "內容": result.extra.get("樣本數")},
            {"項目": "p 值", "內容": round(result.p_value, 4)},
            {"項目": "顯著水準 α", "內容": alpha},
            {"項目": "是否顯著", "內容": "是" if result.significant else "否"},
            {"項目": "Cramér's V", "內容": round(v, 4) if v == v else None},
            {"項目": "效果量強度", "內容": result.effect_size.get("強度")},
            {"項目": "中文解釋", "內容": result.interpretation},
            {"項目": "注意事項", "內容": "；".join(result.warnings) or "無"},
        ]
    )
    state.register_export_table(f"卡方檢定_{col_a}x{col_b}", summary)
    st.caption("此檢定結果已加入匯出清單，可到「📥 匯出」頁一併下載。")
