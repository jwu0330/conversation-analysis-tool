"""Streamlit session state 共用工具：跨分頁存取已上傳的資料與分析結果。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

_DF_KEY = "df"
_META_KEY = "meta"
_EXPORT_KEY = "export_tables"


def set_dataframe(df: pd.DataFrame, meta: dict) -> None:
    """儲存目前分析用的 DataFrame 與來源資訊（原始資料不被覆蓋）。"""
    st.session_state[_DF_KEY] = df
    st.session_state[_META_KEY] = meta


def get_dataframe() -> pd.DataFrame | None:
    return st.session_state.get(_DF_KEY)


def get_meta() -> dict:
    return st.session_state.get(_META_KEY, {})


def has_data() -> bool:
    df = get_dataframe()
    return df is not None and not df.empty


def require_data() -> pd.DataFrame:
    """分頁開頭呼叫：沒有資料就提示並停止該頁執行。"""
    df = get_dataframe()
    if df is None or df.empty:
        st.warning("尚未載入資料，請先回「首頁」上傳 Excel／CSV 或載入內建資料。")
        st.stop()
    return df


def register_export_table(name: str, df: pd.DataFrame) -> None:
    """把想匯出的表格暫存起來，供「📥 匯出」頁一次輸出。"""
    tables = st.session_state.setdefault(_EXPORT_KEY, {})
    tables[name] = df


def get_export_tables() -> dict:
    return st.session_state.get(_EXPORT_KEY, {})


def clear_export_tables() -> None:
    st.session_state[_EXPORT_KEY] = {}
