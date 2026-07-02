"""資料上傳頁：上傳、選工作表、資料摘要、缺漏值/重複檢查、預覽、欄位型態。

也可一鍵載入專案內建的範例資料，方便快速試用。
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from src import state
from src.core import column_types, data_loader, data_quality

st.set_page_config(page_title="資料上傳", page_icon="📤", layout="wide")
st.title("📤 資料上傳")

SAMPLE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sample_data",
    "conversation_sample.xlsx",
)

# --- 上傳區 + 範例資料按鈕 ---
c_up, c_demo = st.columns([3, 2])
with c_up:
    uploaded = st.file_uploader(
        "上傳對話紀錄檔（支援 .xlsx / .xls / .csv）",
        type=["xlsx", "xls", "xlsm", "csv"],
    )
with c_demo:
    st.write("")
    st.write("沒有資料？先用內建範例試玩：")
    if st.button("🎯 載入內建範例資料（320 筆模擬對話紀錄）", type="primary"):
        if os.path.exists(SAMPLE_PATH):
            demo_df = pd.read_excel(SAMPLE_PATH, engine="openpyxl")
            state.set_dataframe(
                demo_df,
                meta={"filename": "conversation_sample.xlsx（內建範例）", "sheet": "Sheet1"},
            )
            state.clear_export_tables()
            st.success("已載入範例資料！")
            st.rerun()
        else:
            st.error(
                "找不到範例檔，請先執行：python sample_data/generate_sample.py"
            )

st.divider()

# --- 決定資料來源：新上傳 > 既有（含範例） ---
if uploaded is not None:
    filename = uploaded.name
    is_excel = data_loader.is_excel(filename)
    sheet_name: str | int = 0
    if is_excel:
        try:
            sheets = data_loader.get_excel_sheets(uploaded)
        except Exception as err:  # noqa: BLE001
            st.error(f"讀取 Excel 工作表失敗：{err}")
            st.stop()
        sheet_name = st.selectbox("選擇要分析的工作表", options=sheets, index=0)
    try:
        df = data_loader.load_any(uploaded, filename, sheet_name=sheet_name)
    except Exception as err:  # noqa: BLE001
        st.error(f"讀取資料失敗：{err}")
        st.stop()
    if df.empty:
        st.warning("讀進來的資料是空的，請確認檔案內容或工作表選擇。")
        st.stop()
    state.set_dataframe(
        df, meta={"filename": filename, "sheet": sheet_name if is_excel else "-"}
    )
elif state.has_data():
    df = state.get_dataframe()
else:
    st.info("請上傳檔案，或點上方「🎯 載入內建範例資料」按鈕即可馬上開始。")
    st.stop()

meta = state.get_meta()
st.caption(f"目前資料來源：**{meta.get('filename', '-')}**（工作表：{meta.get('sheet', '-')}）")

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

# --- 資料預覽（放在最上面，一進來就看得到）---
st.subheader("資料預覽")
n_preview = st.slider("預覽筆數", 5, min(200, len(df)), min(20, len(df)))
st.dataframe(df.head(n_preview), width="stretch")

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
    with st.expander(
        f"重複資料明細（{dup['duplicate_rows']} 列，佔 {dup['duplicate_ratio_pct']}%）"
    ):
        st.dataframe(data_quality.duplicate_rows(df), width="stretch")

st.success("資料已載入，可前往左側其他分頁進行分析。")
