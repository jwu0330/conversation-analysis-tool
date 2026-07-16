"""統計分析頁：SPSS 式共變數分析 ANCOVA（一鍵，完全對齊吳書豪《量化統計方法實作》講義）。

版面分兩區：
  ▍重要區（依講義順序，必報）：描述統計 → 常態性 → Levene → 斜率同質 →
      ANCOVA 型III 完整表 → 調整後平均數 → APA 彙整表
  ▍補充區（本工具加值）：效果量判準、事後 LSD、文章寫法、假設違反處理建議
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import state
from src.core import ancova, column_types, kcr_metrics, stat_tests

st.set_page_config(page_title="統計分析", page_icon="📐", layout="wide")
st.title("📐 統計分析")
st.caption("依研究問題選擇推論方法；欄位順序固定為：判斷向度 → 分組基準／觀察單位 → α。")

df = state.require_data()
num_cols = column_types.numeric_columns(df)
cat_cols = column_types.categorical_columns(df)


def _student_column() -> str | None:
    return next((c for c in ["學生ID", "學生", "student_id", "student"] if c in df.columns), None)


def _numeric_outcomes() -> list[str]:
    """偵測可穩定轉成數字的欄位，包含 Excel 中以文字儲存的數字。"""
    found: list[str] = []
    for col in df.columns:
        source = df[col].dropna()
        if source.empty:
            continue
        parsed = pd.to_numeric(source, errors="coerce")
        if parsed.notna().sum() >= 2 and parsed.notna().mean() >= 0.9:
            found.append(col)
    return found


def _group_candidates(min_groups: int, max_groups: int | None = None) -> list[str]:
    student = _student_column()
    choices: list[str] = []
    for col in df.columns:
        if col == student:
            continue
        # 組間檢定要求每位學生只能屬於一組；K/C/R 等逐題狀態不可拿來分組。
        if student and df[[student, col]].dropna().groupby(student)[col].nunique().max() > 1:
            continue
        counts = df[col].dropna().value_counts()
        k = len(counts)
        if k < min_groups or (max_groups is not None and k > max_groups):
            continue
        if len(counts) and int(counts.min()) >= 2:
            choices.append(col)
    return choices


def _outcome_options() -> tuple[list[str], dict[str, str]]:
    options = [f"raw::{c}" for c in _numeric_outcomes()]
    labels = {f"raw::{c}": f"原始數值：{c}" for c in _numeric_outcomes()}
    kcr = kcr_metrics.student_metrics(df)
    for key, label in kcr_metrics.METRIC_LABELS.items():
        if key in kcr and kcr[key].notna().any():
            option = f"kcr::{key}"
            options.append(option)
            labels[option] = f"衍生指標：{label}"
    return options, labels


def _analysis_frame(option: str, group_col: str) -> tuple[pd.DataFrame, str]:
    """依觀察單位整理；同一學生有多列時先取學生平均。"""
    student = _student_column()
    if option.startswith("kcr::"):
        value_col = option.split("::", 1)[1]
        metrics = kcr_metrics.student_metrics(df, student_col=student, group_col=group_col)
        metrics = metrics.rename(columns={"組別": "分析組別", value_col: "分析值"})
        return metrics, "分析值"

    source_col = option.split("::", 1)[1]
    work = pd.DataFrame({
        "分析組別": df[group_col],
        "分析值": pd.to_numeric(df[source_col], errors="coerce"),
    })
    if student:
        work[student] = df[student]
        work = work.dropna(subset=[student, "分析組別"]).groupby(
            [student, "分析組別"], as_index=False
        )["分析值"].mean()
    return work, "分析值"

method = st.radio(
    "分析方法",
    ["兩組 t 檢定", "多組 ANOVA", "重複計數 Friedman", "共變數分析 ANCOVA"],
    horizontal=True,
)


def _show_result(r, symbol: str, alpha: float) -> bool:
    """顯示共同檢定結果；回傳是否有可用結果。"""
    if r.p_value != r.p_value:
        st.error(r.interpretation)
        for warning in r.warnings:
            st.warning(warning)
        return False
    box = st.success if r.significant else st.info
    sign = "<" if r.significant else "≥"
    text = "達顯著" if r.significant else "未達顯著"
    box(f"{symbol} = {r.statistic:.3f}，p = {r.p_value:.4f} {sign} {alpha}，{text}。")
    st.markdown(f"**方法**：{r.method}")
    st.markdown(f"**解釋**：{r.interpretation}")
    if r.warnings:
        st.warning("\n".join(f"- {w}" for w in r.warnings))
    return True


# ── 兩組 t 檢定：判斷向度 → 分組基準 → α ─────────────────
if method == "兩組 t 檢定":
    st.subheader("兩組平均數比較")
    st.caption("觀測向度會自動列出所有可解析的數值欄位，並附加 K/C/R 衍生指標；同一學生有多列時先彙整為學生平均。")
    outcomes, outcome_labels = _outcome_options()
    groups_2 = _group_candidates(2, 2)
    if not outcomes or not groups_2:
        st.warning("需要至少一個可解析的數值／KCR 指標，以及一個剛好兩組且每組至少兩筆的分組欄位。")
        st.stop()
    c1, c2, c3 = st.columns([3.2, 2, 1])
    value_option = c1.selectbox(
        "觀測向度", outcomes, format_func=lambda key: outcome_labels[key], key="tt_value",
    )
    default_group = groups_2.index("組別") if "組別" in groups_2 else 0
    group_col = c2.selectbox("分組基準（剛好 2 組）", groups_2, index=default_group, key="tt_group")
    alpha = c3.selectbox("α", [0.05, 0.01, 0.10], key="tt_alpha")
    analysis_df, value_col = _analysis_frame(value_option, group_col)
    valid_n = int(analysis_df[value_col].notna().sum())
    st.info(
        f"設定 → 觀測向度：**{outcome_labels[value_option]}** ｜ "
        f"分組基準：**{group_col}** ｜ 有效觀察單位：**{valid_n}** ｜ α = {alpha}"
    )
    if st.button("執行 t 檢定", type="primary"):
        r = stat_tests.independent_t_test(analysis_df, value_col, "分析組別", alpha=alpha)
        if _show_result(r, "t", alpha):
            summary = pd.DataFrame([{"項目": k, "內容": v} for k, v in r.extra.items()])
            state.register_export_table(f"t檢定_{value_col}_by_組別", summary)
    st.stop()


# ── 多組 ANOVA：欄位位置與 t 檢定完全一致 ──────────────────
if method == "多組 ANOVA":
    st.subheader("三組以上平均數比較")
    st.caption("觀測向度與 t 檢定共用相同的自動偵測規則；分組基準必須有三組以上，且每組至少兩筆。")
    outcomes, outcome_labels = _outcome_options()
    groups_3 = _group_candidates(3, 20)
    if not outcomes or not groups_3:
        st.warning("目前資料沒有可用的三組以上分組欄位；兩組資料請使用 t 檢定。")
        st.stop()
    c1, c2, c3 = st.columns([3.2, 2, 1])
    value_option = c1.selectbox(
        "觀測向度", outcomes, format_func=lambda key: outcome_labels[key], key="anova_value"
    )
    group_col = c2.selectbox("分組基準（3–20 組）", groups_3, key="anova_group")
    alpha = c3.selectbox("α", [0.05, 0.01, 0.10], key="anova_alpha")
    analysis_df, value_col = _analysis_frame(value_option, group_col)
    valid_n = int(analysis_df[value_col].notna().sum())
    st.info(f"設定 → 觀測向度：**{outcome_labels[value_option]}** ｜ 分組基準：**{group_col}** ｜ 有效觀察單位：**{valid_n}** ｜ α = {alpha}")
    if st.button("執行 ANOVA", type="primary"):
        r = stat_tests.one_way_anova(analysis_df, value_col, "分析組別", alpha=alpha)
        if _show_result(r, "F", alpha):
            st.dataframe(r.extra["描述統計"], width="stretch", hide_index=True)
            st.dataframe(r.extra["ANOVA表"], width="stretch", hide_index=True)
            if r.extra.get("Tukey事後") is not None:
                posthoc = r.extra["採用方法"].split(" + ")[-1]
                st.markdown(f"**{posthoc} 事後兩兩比較**")
                st.dataframe(r.extra["Tukey事後"], width="stretch", hide_index=True)
            state.register_export_table(f"ANOVA_{value_col}_by_{group_col}", r.extra["ANOVA表"])
            state.register_export_table(f"ANOVA描述_{value_col}_by_{group_col}", r.extra["描述統計"])
    st.stop()


# ── Friedman：獨立方法，不再放在 ANOVA 裡 ──────────────────
if method == "重複計數 Friedman":
    st.subheader("同一觀察單位跨多類別的計數比較")
    st.caption("觀察單位＝誰被重複比較（通常是學生）；判斷向度＝比較哪些類別的出現次數（例如知識點）。")
    if len(cat_cols) < 2:
        st.warning("需要至少兩個分類欄位。")
        st.stop()
    c1, c2, c3 = st.columns([2, 2, 1])
    unit = c1.selectbox(
        "觀察單位（誰被重複比較）", cat_cols,
        index=cat_cols.index("學生") if "學生" in cat_cols else 0,
        key="friedman_unit",
    )
    category_options = [c for c in cat_cols if c != unit]
    category = c2.selectbox("判斷向度（比較的類別）", category_options, key="friedman_category")
    alpha = c3.selectbox("α", [0.05, 0.01, 0.10], key="friedman_alpha")
    st.info(f"設定 → 觀察單位：**{unit}** ｜ 判斷向度：**{category}** ｜ α = {alpha}")
    if st.button("執行 Friedman 檢定", type="primary"):
        r = stat_tests.friedman_count_test(df, unit, category, alpha=alpha)
        if _show_result(r, "χ²", alpha):
            matrix = r.extra["計數矩陣"]
            st.dataframe(matrix, width="stretch", hide_index=True)
            summary = pd.DataFrame([{
                "觀察單位數": r.extra["觀察單位數"], "類別數": r.extra["類別數"],
                "自由度": r.extra["自由度"], "χ²": r.statistic, "p值": r.p_value,
                "Kendall's W": r.effect_size["Kendall's W"],
            }])
            state.register_export_table(f"Friedman_{category}_by_{unit}", summary)
            state.register_export_table(f"Friedman計數矩陣_{category}_by_{unit}", matrix)
    st.stop()


# ── ANCOVA ─────────────────────────────────────────────────
st.subheader("共變數分析 ANCOVA")
st.caption("完全對照吳書豪《量化統計方法實作》SPSS 講義：前測=共變量、後測=依變數、組別=自變數，型 III 平方和。")

if not num_cols or not cat_cols:
    st.warning("ANCOVA 需要：至少 1 個類別欄位（組別）、至少 2 個數值欄位（後測＋前測）。")
    st.stop()


def _guess(cands: list[str], keys: list[str], fallback_idx: int = 0) -> str:
    for kw in keys:
        for c in cands:
            if kw in str(c).lower():
                return c
    return cands[fallback_idx] if cands else ""


default_dv = _guess(num_cols, ["後測", "post", "成績", "score"], -1)
default_cov = _guess([c for c in num_cols if c != default_dv] or num_cols, ["前測", "pre", "先備"], 0)
default_group = _guess(cat_cols, ["組別", "group", "班級", "class", "實驗"], 0)

with st.expander("⚙️ 進階設定（編輯預設變數與參數；不展開就用預設路徑）"):
    dv = st.selectbox("依變數（後測，連續）", num_cols,
                      index=num_cols.index(default_dv) if default_dv in num_cols else 0)
    group = st.selectbox("固定因子／組別（實驗vs對照、班級…）", cat_cols,
                         index=cat_cols.index(default_group) if default_group in cat_cols else 0)
    cov_opts = [c for c in num_cols if c != dv]
    default_covs = [default_cov] if default_cov in cov_opts else cov_opts[:1]
    covars = st.multiselect("共變量（前測，連續，可多選）", cov_opts, default=default_covs)
    alpha = st.selectbox("顯著水準 α", [0.05, 0.01, 0.10], index=0)

st.info(
    f"設定 →　依變數(後測)：**{dv}**　｜　組別：**{group}**　｜　"
    f"共變量(前測)：**{', '.join(covars) if covars else '（尚未選）'}**　｜　α = {alpha}"
)
st.caption("提醒（講義 p30）：前測**不要**單獨跑 t 檢定證明組別同質，直接以前測作共變量進 ANCOVA。")

if not st.button("▶️ 一鍵執行 ANCOVA（跑完整 SPSS 流程）", type="primary"):
    st.caption("按上方按鈕即依講義流程一次跑完。預設會自動帶入前測／後測／組別。")
    st.stop()

if not covars:
    st.error("請至少選一個共變量（前測）。到進階設定選。")
    st.stop()
try:
    res = ancova.run_ancova(df, dv, group, covars, alpha=alpha)
except Exception as err:  # noqa: BLE001
    st.error(f"ANCOVA 執行失敗：{err}")
    st.stop()

st.success(f"完成：{group} 共 {len(res.groups)} 組（{', '.join(res.groups)}），有效樣本 n = {res.n_total}。")

# ══════════════════════════ 重要區（依講義順序） ══════════════════════════
st.header("▍重要區（依講義流程與必報項目）")

# ① 描述統計
st.subheader("① 各組描述統計（N、平均數、標準差）")
st.dataframe(res.descriptives, width="stretch", hide_index=True)
state.register_export_table("ANCOVA_1_描述統計", res.descriptives)

# ② 常態性
st.subheader("② 常態性檢定（Shapiro-Wilk n<50／Kolmogorov-Smirnov n≥50）")
st.dataframe(res.normality, width="stretch", hide_index=True)
if res.normality_ok:
    st.success("✅ 各組皆通過常態性假設（p ≥ α）。")
else:
    st.warning("⚠️ 有組別未通過常態性 → 依講義改用無母數檢定（Mann-Whitney U）。")
state.register_export_table("ANCOVA_2_常態性", res.normality)

# ③ Levene
st.subheader("③ 變異數同質性檢定（Levene，以平均為中心）")
lv = res.levene
c = st.columns(4)
c[0].metric("F", lv["F"])
c[1].metric("df1 / df2", f"{lv['df1']} / {lv['df2']}")
c[2].metric("p 值", lv["p值"])
c[3].metric("變異數同質", "✅ 是" if lv["同質(p≥α)"] else "⚠️ 否")
if not lv["同質(p≥α)"]:
    st.warning("⚠️ 變異數不同質 → 依講義：前後測都改跑 t 檢定處理。")
state.register_export_table("ANCOVA_3_Levene", pd.DataFrame([lv]))

# ④ 斜率同質
st.subheader("④ 組內迴歸係數同質性檢定（組別 × 前測 交乘項，放最後；型 III）")
st.caption("交乘項 p ≥ α 代表各組斜率一致，符合 ANCOVA 前提（Reviewer 常問：IV 對共變量是否有顯著影響）。")
st.dataframe(res.slope_homogeneity, width="stretch", hide_index=True)
if res.slope_ok:
    st.success("✅ 組內迴歸係數同質，適合使用 ANCOVA。")
else:
    st.error("❌ 組內迴歸係數不同質 → 依講義：改用詹森-內曼法（Johnson-Neyman）。")
state.register_export_table("ANCOVA_4_斜率同質性", res.slope_homogeneity)

# ⑤ 主分析 ANCOVA 型III
st.subheader("⑤ 主分析：ANCOVA 主旨間效果檢定（完全因子設計、型 III 平方和）")
st.dataframe(res.ancova_table, width="stretch", hide_index=True)
st.caption(f"R² = {res.r_squared}（調整後 R² = {res.r_squared_adj}）")
if res.group_p < alpha:
    st.success(f"✅ 控制前測後，組別主效果顯著：F = {res.group_F}, p = {res.group_p} < {alpha}，"
               f"局部 η² = {res.group_eta2}（{res.eta2_magnitude}）。")
else:
    st.info(f"ℹ️ 控制前測後，組別主效果未達顯著：F = {res.group_F}, p = {res.group_p}。")
state.register_export_table("ANCOVA_5_主旨間效果檢定", res.ancova_table)

# ⑥ 調整後平均數
st.subheader("⑥ 調整後平均數（EMMeans）")
st.caption(res.adjusted_means.attrs.get("說明", "") + "　※ ANCOVA 一定要報告調整後平均數與標準誤。")
st.dataframe(res.adjusted_means, width="stretch", hide_index=True)
state.register_export_table("ANCOVA_6_調整後平均", res.adjusted_means)

# ⑦ APA 彙整表
st.subheader("⑦ APA 彙整表（可直接放進論文）")
st.caption("欄位＝Group｜N｜Mean｜SD｜Adjusted Mean｜Adjusted SD｜F｜η²（依講義慣例，Adjusted SD 欄填調整後標準誤 SE）。* p < .05")
st.dataframe(res.summary_apa, width="stretch", hide_index=True)
state.register_export_table("ANCOVA_7_APA彙整表", res.summary_apa)

# ══════════════════════════ 補充區 ══════════════════════════
st.header("▍補充區（加值，非講義必列）")

with st.expander("效果量 η² 判準（Cohen, 1988）"):
    st.markdown("- .01 ≤ η² < .059：**小效果**\n- .059 ≤ η² < .138：**中效果**\n- η² ≥ .138：**大效果**")

with st.expander("事後兩兩比較（LSD，無校正；對照講義選項的信賴區間調整＝LSD）"):
    st.dataframe(res.posthoc, width="stretch", hide_index=True)
    state.register_export_table("ANCOVA_補_事後LSD", res.posthoc)

with st.expander("📝 文章寫法（可直接改寫進論文）", expanded=True):
    st.markdown(f"**中文**：{res.article_zh}")
    st.markdown(f"**English**：{res.article_en}")
    article_tbl = pd.DataFrame(
        [{"語言": "中文", "內容": res.article_zh}, {"語言": "English", "內容": res.article_en}]
    )
    state.register_export_table("ANCOVA_補_文章寫法", article_tbl)

if res.decisions:
    st.subheader("⚠️ 假設違反的處理建議（依講義 p48）")
    for d in res.decisions:
        st.warning(d)

if res.warnings:
    st.caption("其他提醒：" + "；".join(res.warnings))

st.caption("以上結果已加入匯出清單，可回「首頁 → 匯出」一併下載。")
