"""資料上傳頁：上傳、選工作表、資料摘要、缺漏值/重複檢查、預覽、欄位型態。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import state
from src.core import column_types, data_loader, data_quality

st.set_page_config(page_title="資料上傳", page_icon="📤", layout="wide")
st.title("📤 資料上傳")

uploaded = st.file_uploader(
    "上傳對話紀錄檔（支援 .xlsx / .xls / .csv）",
    type=["xlsx", "xls", "xlsm", "csv"],
)

if uploaded is None:
    st.info("請選擇檔案。若手邊沒有資料，可用專案內 `sample_data/` 的模擬資料測試。")
    st.stop()

filename = uploaded.name
is_excel = data_loader.is_excel(filename)

# --- 工作表選擇（Excel）---
sheet_name: str | int = 0
if is_excel:
    try:
        sheets = data_loader.get_excel_sheets(uploaded)
    except Exception as err:  # noqa: BLE001
        st.error(f"讀取 Excel 工作表失敗：{err}")
        st.stop()
    sheet_name = st.selectbox("選擇要分析的工作表", options=sheets, index=0)

# --- 讀取 ---
try:
    df = data_loader.load_any(uploaded, filename, sheet_name=sheet_name)
except Exception as err:  # noqa: BLE001
    st.error(f"讀取資料失敗：{err}")
    st.stop()

if df.empty:
    st.warning("讀進來的資料是空的，請確認檔案內容或工作表選擇。")
    st.stop()

# 存進 session_state（原始資料保留，不覆蓋）
state.set_dataframe(
    df,
    meta={"filename": filename, "sheet": sheet_name if is_excel else "-"},
)

# --- 基本摘要 ---
summary = data_quality.basic_summary(df)
dup = data_quality.duplicate_report(df)
total_missing = int(df.isna().sum().sum())

st.subheader("資料摘要")
c1, c2, c3, c4 = st.columns(4)
c1.metric("資料筆數", summary["rows"])
c2.metric("欄位數", summary["cols"])
c3.metric("缺漏值總數", total_missing)
c4.metric("重複資料列", dup["duplicate_rows"])

# --- 欄位型態 ---
st.subheader("欄位一覽與自動辨識型態")
types = column_types.infer_types(df)
type_table = pd.DataFrame(
    {
        "欄位": list(types.keys()),
        "型態": [column_types.TYPE_LABELS_ZH[t] for t in types.values()],
        "不重複值數": [int(df[c].nunique(dropna=True)) for c in types],
        "缺漏數": [int(df[c].isna().sum()) for c in types],
    }
)
st.dataframe(type_table, width="stretch", hide_index=True)
st.caption("型態辨識僅為建議：分組/交叉分析建議用「類別」欄位，數值統計用「數值」欄位。")

# --- 缺漏值明細 ---
with st.expander("缺漏值明細"):
    miss = data_quality.missing_report(df)
    st.dataframe(miss, width="stretch", hide_index=True)

# --- 重複資料明細 ---
if dup["duplicate_rows"] > 0:
    with st.expander(f"重複資料明細（{dup['duplicate_rows']} 列，佔 {dup['duplicate_ratio_pct']}%）"):
        st.dataframe(data_quality.duplicate_rows(df), width="stretch")

# --- 預覽 ---
st.subheader("資料預覽")
n_preview = st.slider("預覽筆數", 5, min(100, len(df)), min(20, len(df)))
st.dataframe(df.head(n_preview), width="stretch")

st.success("資料已載入，可前往左側其他分頁進行分析。")
