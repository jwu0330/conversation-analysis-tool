"""序列分析專用圖表（Plotly，獨立於 src/core/charts）。"""
from __future__ import annotations

import math

import graphviz
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.sequence.analysis import level_label

_TEMPLATE = "plotly_white"

# 節點配色：低階偏藍、高階偏紅，方便肉眼區分認知層次
_LEVEL_COLOR = {
    0: "#95A5A6", 1: "#5DADE2", 2: "#3498DB", 3: "#2E86C1",
    4: "#EC7063", 5: "#E74C3C", 6: "#C0392B",
}


def transition_sankey(trans_group: pd.DataFrame, title: str = "") -> go.Figure:
    """某一組的節點轉移 Sankey 圖。

    trans_group: 欄位含 Source、Target、次數（單一組別）。
    來源與目標節點分左右兩欄，避免自我迴圈把圖畫亂。
    """
    if trans_group.empty:
        return _empty_fig(title)

    src_levels = sorted(trans_group["Source"].unique())
    tgt_levels = sorted(trans_group["Target"].unique())

    labels, colors, node_index = [], [], {}
    for lv in src_levels:
        node_index[("s", lv)] = len(labels)
        labels.append(f"{level_label(int(lv))}（前題）")
        colors.append(_LEVEL_COLOR.get(int(lv), "#7F8C8D"))
    for lv in tgt_levels:
        node_index[("t", lv)] = len(labels)
        labels.append(f"{level_label(int(lv))}（後題）")
        colors.append(_LEVEL_COLOR.get(int(lv), "#7F8C8D"))

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(label=labels, color=colors, pad=18, thickness=18),
            link=dict(
                source=[node_index[("s", r.Source)] for r in trans_group.itertuples()],
                target=[node_index[("t", r.Target)] for r in trans_group.itertuples()],
                value=[r.次數 for r in trans_group.itertuples()],
            ),
        )
    )
    fig.update_layout(title=title, template=_TEMPLATE, font_size=12)
    return fig


def _ring_positions(levels: list[int], radius: float = 1.6) -> dict[int, tuple[float, float]]:
    """把各 Level 均勻釘在圓周上（6 個即成六邊形），由高到低順時針排列。"""
    ordered = sorted(levels)
    n = max(len(ordered), 1)
    pos: dict[int, tuple[float, float]] = {}
    for i, lv in enumerate(ordered):
        angle = math.radians(90 - i * 360.0 / n)  # 從頂端開始，順時針
        pos[lv] = (round(radius * math.cos(angle), 3), round(radius * math.sin(angle), 3))
    return pos


def transition_graph(
    trans_group: pd.DataFrame,
    levels: list[int],
    high_min: int = 4,
    ordinal: bool = True,
) -> graphviz.Digraph:
    """節點轉移網絡圖（節點位置固定成六邊形）。

    - 節點：圓圈釘在圓周固定位置（跨組一致，不會每次亂飄）。
      顏色 🔵藍=低階、🔴紅=高階（以 high_min 為界）。
    - 箭頭方向配色：綠=往較高碼、橘=往較低碼、灰=同碼(自我迴圈)。
    - 箭頭粗細與數字 = 轉移次數。
    傳給 st.graphviz_chart() 顯示；用 neato 引擎才能吃固定座標。
    """
    up_c, down_c, loop_c = "#27AE60", "#E67E22", "#95A5A6"
    low_c, high_c = "#5DADE2", "#E74C3C"
    # ⚠️【暫時性產物 2026-07】：節點是「知識點」而非 SOLO 層級，藍/紅高低階上色
    #   對知識點沒有意義，故先停用、統一中性灰。★ 恢復方式同 gseq_graph（見該處註解）。
    # low_c, high_c = "#5DADE2", "#E74C3C"
    neutral_c = "#7F8C8D"  # 暫時：所有節點統一中性灰

    g = graphviz.Digraph(engine="neato")
    g.attr(bgcolor="white", outputorder="edgesfirst", overlap="false",
           sep="+8", margin="0.2")
    g.attr(
        "node", shape="circle", style="filled", fontcolor="white",
        fontsize="10", width="0.62", fixedsize="true", penwidth="0",
    )

    positions = _ring_positions(levels)
    for lv in sorted(levels):
        x, y = positions[lv]
        # ⚠️ 暫時：統一中性灰（原：fill = high_c if lv >= high_min else low_c）
        fill = (high_c if lv >= high_min else low_c) if ordinal else neutral_c
        g.node(level_label(lv), label=level_label(lv), pos=f"{x},{y}!", fillcolor=fill)

    if not trans_group.empty:
        max_count = max(int(trans_group["次數"].max()), 1)
        for r in trans_group.itertuples():
            width = 0.8 + 3.0 * (r.次數 / max_count)
            if not ordinal:
                color = loop_c
            elif r.Target > r.Source:
                color = up_c
            elif r.Target < r.Source:
                color = down_c
            else:
                color = loop_c
            g.edge(
                level_label(int(r.Source)), level_label(int(r.Target)), label=f" {r.次數}",
                penwidth=f"{width:.2f}", color=color, fontcolor=color, fontsize="10",
            )
    return g


def transition_heatmap(matrix: pd.DataFrame, title: str = "") -> go.Figure:
    """轉移矩陣熱圖（列=前題 Source，欄=後題 Target）。"""
    fig = px.imshow(
        matrix,
        text_auto=True,
        aspect="auto",
        color_continuous_scale="Blues",
        labels=dict(x="後題 Target", y="前題 Source", color="值"),
        title=title,
    )
    fig.update_layout(template=_TEMPLATE)
    return fig


def highlow_bar(highlow: pd.DataFrame, title: str = "") -> go.Figure:
    """高低階四種轉移的分組長條圖（以組內比例呈現）。"""
    if highlow.empty:
        return _empty_fig(title)
    d = highlow.copy()
    d["轉移"] = d["Source"] + " → " + d["Target"]
    fig = px.bar(
        d, x="轉移", y="組內比例(%)", color="組別", barmode="group",
        title=title, template=_TEMPLATE,
        category_orders={"轉移": ["低階 → 低階", "低階 → 高階", "高階 → 高階", "高階 → 低階"]},
    )
    return fig


def position_line(profile: pd.DataFrame, title: str = "") -> go.Figure:
    """題序流動圖：各組平均節點碼隨題序變化（僅對有序的層級型節點有意義）。"""
    if profile.empty:
        return _empty_fig(title)
    fig = px.line(
        profile, x="題序", y="平均層級", color="組別", markers=True,
        title=title, template=_TEMPLATE,
    )
    fig.update_yaxes(title="平均節點碼")
    fig.update_xaxes(dtick=1)
    return fig


def _empty_fig(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title or "（無足夠資料繪圖）",
        template=_TEMPLATE,
        annotations=[dict(text="資料不足，無法繪圖", showarrow=False, font_size=16)],
    )
    return fig


# 組別配色（實驗/對照或其他），依出現順序循環
_GROUP_PALETTE = ["#2E86C1", "#E67E22", "#27AE60", "#8E44AD", "#16A085"]


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def trend_figure(
    points: pd.DataFrame,
    bands: dict,
    high_min: int,
    level_min: int,
    level_max: int,
    show_band: bool = True,
    show_zones: bool = True,
    title: str = "",
) -> go.Figure:
    """題序 × 節點碼 趨勢圖：散布點 + 每組迴歸線(含信賴區帶) + 高低階底色。

    （趨勢／高低階僅對「有序的層級型節點」有意義；名目型知識點請看轉移分析。）
    points: 欄位 學生、組別、題序、層級。
    bands:  {組別: regression_band() 的回傳 dict 或 None}。
    """
    fig = go.Figure()
    groups = list(dict.fromkeys(points["組別"].tolist()))
    color_of = {g: _GROUP_PALETTE[i % len(_GROUP_PALETTE)] for i, g in enumerate(groups)}
    rng = np.random.default_rng(0)  # 固定種子 → 抖動可重現

    # 高低階底色帶
    if show_zones:
        fig.add_hrect(y0=high_min - 0.5, y1=level_max + 0.5,
                      fillcolor="rgba(231,76,60,0.07)", line_width=0, layer="below")
        fig.add_hrect(y0=level_min - 0.5, y1=high_min - 0.5,
                      fillcolor="rgba(93,173,226,0.07)", line_width=0, layer="below")

    for g in groups:
        c = color_of[g]
        sub = points[points["組別"] == g]
        jitter = rng.uniform(-0.12, 0.12, size=len(sub))
        # 散布點
        fig.add_trace(go.Scatter(
            x=sub["題序"] + jitter, y=sub["層級"], mode="markers",
            name=f"{g}（提問）", legendgroup=g,
            marker=dict(color=_hex_to_rgba(c, 0.45), size=6),
            hovertemplate="題序%{x:.0f}<br>節點碼 %{y}<extra></extra>",
        ))
        band = bands.get(g)
        if band is not None:
            if show_band:
                fig.add_trace(go.Scatter(
                    x=np.concatenate([band["x"], band["x"][::-1]]),
                    y=np.concatenate([band["hi"], band["lo"][::-1]]),
                    fill="toself", fillcolor=_hex_to_rgba(c, 0.15),
                    line=dict(width=0), hoverinfo="skip",
                    name=f"{g} 95%信賴區", legendgroup=g, showlegend=False,
                ))
            fig.add_trace(go.Scatter(
                x=band["x"], y=band["y"], mode="lines",
                line=dict(color=c, width=3),
                name=f"{g} 迴歸線 (斜率={band['slope']:.3f})", legendgroup=g,
            ))

    fig.update_layout(title=title, template=_TEMPLATE, xaxis_title="題序（第幾題）",
                      yaxis_title="節點碼", hovermode="closest")
    fig.update_yaxes(dtick=1, range=[level_min - 0.6, level_max + 0.6])
    fig.update_xaxes(dtick=1)
    return fig


def student_slope_box(slopes: pd.DataFrame, title: str = "") -> go.Figure:
    """每位學生迴歸斜率的箱型圖，比較各組（斜率>0＝該生提問逐步深化）。"""
    if slopes.empty:
        return _empty_fig(title)
    fig = px.box(slopes, x="組別", y="斜率", color="組別", points="all",
                 title=title, template=_TEMPLATE,
                 hover_data=["學生", "提問數"])
    fig.add_hline(y=0, line_dash="dash", line_color="#7F8C8D",
                  annotation_text="斜率=0（無升降趨勢）")
    fig.update_yaxes(title="個別學生迴歸斜率")
    return fig


def gseq_graph(
    gseq_group: pd.DataFrame,
    levels: list[int],
    high_min: int = 4,
    only_significant: bool = True,
    z_crit: float = 1.96,
) -> graphviz.Digraph:
    """GSEQ 事件轉移圖（六邊形固定位置，線上標調整後殘差 z）。

    仿標準滯後序列分析工具的「事件轉移圖」：
    - 節點：圓圈（顏色目前統一中性灰，見下方暫時性註解），位置固定。
    - only_significant=True ：只畫 |z|>z_crit 的顯著轉移。
    - only_significant=False：畫出所有實際發生的轉移；顯著者上色標 z、未達顯著者淡灰細線。
    - 配色：🔴紅實線=顯著偏多、🟠橘虛線=顯著偏少、⚪淡灰細線=未達顯著。
    """
    # ⚠️【暫時性產物 2026-07】：節點是「知識點」而非 SOLO 認知層級，原本用
    #   high_min 分高/低階並上藍(#5DADE2)/紅(#E74C3C)，對知識點沒有意義，故先停用、
    #   統一中性灰。★ 日後若有顏色需求（例如依知識點主題分群上色）：取消下一行註解、
    #   把 fill 那行改回 `high_c if lv >= high_min else low_c` 即可恢復。
    # low_c, high_c = "#5DADE2", "#E74C3C"
    neutral_c = "#7F8C8D"  # 暫時：所有節點統一中性灰
    up_c, down_c, ns_c = "#C0392B", "#E67E22", "#BDC3C7"
    g = graphviz.Digraph(engine="neato")
    g.attr(bgcolor="white", outputorder="edgesfirst", overlap="false",
           sep="+8", margin="0.2")
    g.attr("node", shape="circle", style="filled", fontcolor="white",
           fontsize="10", width="0.62", fixedsize="true", penwidth="0")

    positions = _ring_positions(levels)
    for lv in sorted(levels):
        x, y = positions[lv]
        # ⚠️ 暫時：統一中性灰（原：fill = high_c if lv >= high_min else low_c）
        fill = neutral_c
        g.node(level_label(lv), label=level_label(lv), pos=f"{x},{y}!", fillcolor=fill)

    df = gseq_group.copy()
    sig_rows = df[df["顯著"] != ""]
    edges = sig_rows if only_significant else df[df["觀察次數"] > 0]
    if edges.empty:
        g.attr(label="（無可繪的轉移）", labelloc="t", fontsize="12")
        return g

    zvals = [abs(float(z)) for z in sig_rows["調整殘差z"] if z is not None]
    max_z = max(zvals) if zvals else 1.0

    for r in edges.itertuples():
        z = r.調整殘差z
        if r.顯著 != "" and z is not None:
            zf = float(z)
            width = 1.0 + 2.8 * (abs(zf) / max_z)
            color, style = (up_c, "solid") if zf > 0 else (down_c, "dashed")
            g.edge(r.Source, r.Target, label=f" {zf:.2f}", penwidth=f"{width:.2f}",
                   color=color, fontcolor=color, style=style, fontsize="10")
        else:
            # 未達顯著：淡灰細線、不標數值，避免干擾
            g.edge(r.Source, r.Target, penwidth="0.7", color=ns_c, arrowsize="0.6")
    return g
