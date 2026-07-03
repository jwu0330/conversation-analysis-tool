"""對話紀錄統計分析系統 — 主程式入口。

執行方式：
    streamlit run app.py

多分頁介面由 pages/ 目錄自動載入（依檔名數字排序）。
"""
from __future__ import annotations

import streamlit as st

from src import datasets, state

st.set_page_config(
    page_title="對話紀錄統計分析系統",
    page_icon="📊",
    layout="wide",
)

st.title("📊 對話紀錄統計分析系統")
st.caption("上傳對話紀錄 → 選欄位 → 選統計方法 → 產生圖表與檢定 → 匯出結果")

st.markdown(
    """
    這是一套讓研究者**不用寫程式、也不用在 Excel 反覆手動計算**的分析工具。
    採「**先選欄位，再選分析**」的流程，所有結果都可重複產生並匯出。

    #### 使用步驟
    1. **📤 資料上傳**：上傳 Excel／CSV，檢查筆數、缺漏值與重複資料。
    2. **🧮 描述統計**：選一個欄位，套用 count／mean／median／std 等統計函數。
    3. **📊 分組比較**：選分組欄位與比較欄位，產生交叉表、百分比表與長條圖。
    4. **🔬 統計檢定**：卡方檢定 + p 值 + Cramér's V 效果量，附中文解釋與注意事項。
    5. **📥 匯出**：把統計表與檢定結果一次匯出成 Excel。

    > 目前為 **第一版 MVP**。後續會擴充 t 檢定、ANOVA、非參數檢定、相關分析、
    > 多分析卡片、知識涵蓋度分析與 HTML 報告匯出。
    """
)

st.divider()

if state.has_data():
    meta = state.get_meta()
    df = state.get_dataframe()
    st.success(
        f"目前已載入：**{meta.get('filename', '(未命名)')}**"
        f"（工作表：{meta.get('sheet', '-')}），"
        f"共 **{df.shape[0]}** 筆、**{df.shape[1]}** 欄。"
    )
    st.info("請從左側選單前往各分析分頁。")
else:
    st.info("👈 尚未載入資料。可從左側「📤 資料上傳」上傳檔案，或直接載入內建資料：")
    builtin = datasets.discover_datasets()
    if builtin:
        labels = [d["label"] for d in builtin]
        choice = st.selectbox("選擇內建資料", labels)
        if st.button("🎯 載入所選內建資料", type="primary"):
            picked = builtin[labels.index(choice)]
            demo_df = datasets.load_dataset(picked["path"])
            state.set_dataframe(
                demo_df,
                meta={"filename": f"{picked['filename']}（內建）", "sheet": "-"},
            )
            state.clear_export_tables()
            st.rerun()
    else:
        st.warning("找不到內建資料，請把檔案放進 `data/`，或執行 "
                   "`python sample_data/generate_sample.py`。")

with st.sidebar:
    st.header("關於")
    st.write("版本：MVP v1")
    st.write("技術：Streamlit · pandas · SciPy · Plotly")
