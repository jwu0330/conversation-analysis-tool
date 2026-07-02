"""匯出頁：把各分頁累積的統計表與檢定結果，連同分析參數一次匯出成 Excel。"""
from __future__ import annotations

import streamlit as st

from src import state
from src.core import exporter

st.set_page_config(page_title="匯出", page_icon="📥", layout="wide")
st.title("📥 匯出分析結果")

df = state.require_data()
meta = state.get_meta()
tables = state.get_export_tables()

st.markdown(
    "你在「描述統計 / 分組比較 / 統計檢定」頁產生的表格會自動累積到這裡，"
    "可連同分析參數一次匯出成單一 Excel 檔。"
)

report_time = st.text_input(
    "分析時間標記（可自行填寫；預設請於下載前輸入）",
    value="",
    placeholder="例如 2026-07-03 14:30",
)

if not tables:
    st.info("目前尚無可匯出的表格。請先到其他分頁執行分析。")
    st.stop()

st.subheader("待匯出的表格")
for name, tbl in tables.items():
    with st.expander(f"{name}（{tbl.shape[0]} 列 × {tbl.shape[1]} 欄）"):
        st.dataframe(tbl, width="stretch")

# 分析參數紀錄
params = {
    "上傳檔案名稱": meta.get("filename", "-"),
    "工作表": meta.get("sheet", "-"),
    "資料筆數": df.shape[0],
    "欄位數": df.shape[1],
    "分析時間": report_time or "(未填)",
    "匯出表格數": len(tables),
    "表格清單": list(tables.keys()),
}
params_frame = exporter.build_params_frame(params)

st.subheader("分析參數紀錄")
st.dataframe(params_frame, width="stretch", hide_index=True)

# 組合所有工作表：參數 + 各表
sheets = {"分析參數": params_frame}
sheets.update(tables)

excel_bytes = exporter.tables_to_excel_bytes(sheets)

fname_base = (meta.get("filename", "分析結果").rsplit(".", 1)[0]) or "分析結果"
st.download_button(
    "⬇️ 下載完整分析結果（Excel）",
    data=excel_bytes,
    file_name=f"{fname_base}_分析結果.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)

col1, col2 = st.columns(2)
with col1:
    if st.button("🗑️ 清空匯出清單"):
        state.clear_export_tables()
        st.rerun()
