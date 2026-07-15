"""對話紀錄統計分析系統 — 首頁（資料上傳 ＋ 資料檢查 ＋ 結果匯出）。

執行方式：
    streamlit run app.py

前端結構（4 界面）：
    首頁（本頁）      上傳資料、資料品質檢查、跑完後在這裡一次匯出
    📈 敘述性統計     描述統計 / 累積排名 / 相關 / t 檢定 / 交叉熱力圖
    📐 統計分析       SPSS 式共變數分析 ANCOVA（一鍵預設流程）
    🔀 序列分析       Bloom 提問序列 / 轉移分析 / 趨勢軌跡
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import datasets, state
from src.core import column_types, data_loader, data_quality, exporter

st.set_page_config(page_title="對話紀錄統計分析系統", page_icon="📊", layout="wide")

st.title("📊 對話紀錄統計分析系統")
st.caption("上傳資料 → 敘述性統計 → 統計分析（ANCOVA） → 序列分析 → 在本頁匯出")

with st.sidebar:
    st.header("關於")
    st.write("版本：v2（前端重構）")
    st.write("技術：Streamlit · pandas · SciPy · statsmodels · pingouin · Plotly")
    st.caption("左側分頁：敘述性統計 / 統計分析 / 序列分析。匯出集中在本首頁。")

tab_upload, tab_export = st.tabs(["📤 資料上傳與檢查", "📥 匯出分析結果"])

# ======================================================================
# 分頁一：資料上傳與檢查
# ======================================================================
with tab_upload:
    c_up, c_demo = st.columns([3, 2])
    with c_up:
        uploaded = st.file_uploader(
            "上傳對話紀錄檔（支援 .xlsx / .xls / .csv）",
            type=["xlsx", "xls", "xlsm", "csv"],
        )
    with c_demo:
        st.write("")
        st.write("或直接載入**內建資料**（放在 `sample_data/` 或 `data/` 的檔案）：")
        builtin = datasets.discover_datasets()
        if builtin:
            labels = [d["label"] for d in builtin]
            choice = st.selectbox("內建資料集", labels, label_visibility="collapsed")
            if st.button("🎯 載入所選內建資料", type="primary"):
                picked = builtin[labels.index(choice)]
                try:
                    demo_df = datasets.load_dataset(picked["path"])
                    state.set_dataframe(
                        demo_df,
                        meta={"filename": f"{picked['filename']}（內建）", "sheet": "-"},
                    )
                    state.clear_export_tables()
                    st.success(f"已載入：{picked['filename']}")
                    st.rerun()
                except Exception as err:  # noqa: BLE001
                    st.error(f"載入失敗：{err}")
        else:
            st.info("目前沒有內建資料。可把檔案放進 `data/`，或執行 "
                    "`python sample_data/generate_sample.py` 產生範例。")

    # 決定資料來源：新上傳 > 既有（含範例）
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
        state.clear_export_tables()

    if not state.has_data():
        st.info("👆 請上傳檔案，或點「🎯 載入所選內建資料」馬上開始。")
    else:
        df = state.get_dataframe()
        meta = state.get_meta()
        st.divider()
        st.success(
            f"目前資料來源：**{meta.get('filename', '-')}**"
            f"（工作表：{meta.get('sheet', '-')}），"
            f"共 **{df.shape[0]}** 筆、**{df.shape[1]}** 欄。可前往左側分頁分析。"
        )

        # --- 摘要 ---
        summary = data_quality.basic_summary(df)
        dup = data_quality.duplicate_report(df)
        total_missing = int(df.isna().sum().sum())
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("資料筆數", summary["rows"])
        m2.metric("欄位數", summary["cols"])
        m3.metric("缺漏值總數", total_missing)
        m4.metric("重複資料列", dup["duplicate_rows"])

        # --- 預覽 ---
        st.subheader("資料預覽")
        n_preview = st.slider("預覽筆數", 5, min(200, len(df)), min(20, len(df)))
        st.dataframe(df.head(n_preview), width="stretch")

        # --- 欄位型態 ---
        with st.expander("欄位一覽與自動辨識型態", expanded=False):
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
            st.caption("分組/交叉分析建議用「類別」欄位，數值統計用「數值」欄位。")

        # --- 缺漏 / 重複明細 ---
        with st.expander("缺漏值明細", expanded=False):
            st.dataframe(data_quality.missing_report(df), width="stretch", hide_index=True)
        if dup["duplicate_rows"] > 0:
            with st.expander(
                f"重複資料明細（{dup['duplicate_rows']} 列，佔 {dup['duplicate_ratio_pct']}%）"
            ):
                st.dataframe(data_quality.duplicate_rows(df), width="stretch")

# ======================================================================
# 分頁二：匯出（各分頁分析結果集中在此下載）
# ======================================================================
with tab_export:
    if not state.has_data():
        st.info("尚未載入資料。請先於「資料上傳與檢查」分頁載入。")
    else:
        df = state.get_dataframe()
        meta = state.get_meta()
        tables = state.get_export_tables()

        st.markdown(
            "你在「敘述性統計 / 統計分析 / 序列分析」頁產生的表格會**自動累積**到這裡，"
            "可連同分析參數一次匯出成單一 Excel。"
        )
        report_time = st.text_input(
            "分析時間標記（可自行填寫）", value="", placeholder="例如 2026-07-15 14:30"
        )

        if not tables:
            st.info("目前尚無可匯出的表格。請先到其他分頁執行分析。")
        else:
            st.subheader("待匯出的表格")
            for name, tbl in tables.items():
                with st.expander(f"{name}（{tbl.shape[0]} 列 × {tbl.shape[1]} 欄）"):
                    st.dataframe(tbl, width="stretch")

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
            if st.button("🗑️ 清空匯出清單"):
                state.clear_export_tables()
                st.rerun()
