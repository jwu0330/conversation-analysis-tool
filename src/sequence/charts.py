"""序列分析專用圖表（Plotly，獨立於 src/core/charts）。"""
from __future__ import annotations

import math

import graphviz
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

_TEMPLATE = "plotly_white"

# 節點配色：低階偏藍、高階偏紅，方便肉眼區分認知層次
_LEVEL_COLOR = {
    0: "#95A5A6", 1: "#5DADE2", 2: "#3498DB", 3: "#2E86C1",
    4: "#EC7063", 5: "#E74C3C", 6: "#C0392B",
}


def transition_sankey(trans_group: pd.DataFrame, title: str = "") -> go.Figure:
    """某一組的 Bloom 轉移 Sankey 圖。

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
        labels.append(f"L{lv}（前題）")
        colors.append(_LEVEL_COLOR.get(int(lv), "#7F8C8D"))
    for lv in tgt_levels:
        node_index[("t", lv)] = len(labels)
        labels.append(f"L{lv}（後題）")
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


def _ring_positions(levels: list[int], radius: float = 2.4) -> dict[int, tuple[float, float]]:
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
) -> graphviz.Digraph:
    """Bloom 轉移網絡圖（節點位置固定成六邊形）。

    - 節點：圓圈釘在圓周固定位置（跨組一致，不會每次亂飄）。
      顏色 🔵藍=低階、🔴紅=高階（以 high_min 為界）。
    - 箭頭方向配色：綠=往較高 Bloom、橘=往較低、灰=同層級(自我迴圈)。
    - 箭頭粗細與數字 = 轉移次數。
    傳給 st.graphviz_chart() 顯示；用 neato 引擎才能吃固定座標。
    """
    up_c, down_c, loop_c = "#27AE60", "#E67E22", "#95A5A6"
    low_c, high_c = "#5DADE2", "#E74C3C"

    g = graphviz.Digraph(engine="neato")
    g.attr(bgcolor="white", outputorder="edgesfirst", overlap="false")
    g.attr(
        "node", shape="circle", style="filled", fontcolor="white",
        fontsize="14", width="0.7", fixedsize="true", penwidth="0",
    )

    positions = _ring_positions(levels)
    for lv in sorted(levels):
        x, y = positions[lv]
        fill = high_c if lv >= high_min else low_c
        g.node(f"L{lv}", label=f"L{lv}", pos=f"{x},{y}!", fillcolor=fill)

    if not trans_group.empty:
        max_count = max(int(trans_group["次數"].max()), 1)
        for r in trans_group.itertuples():
            width = 1.0 + 5.0 * (r.次數 / max_count)
            if r.Target > r.Source:
                color = up_c
            elif r.Target < r.Source:
                color = down_c
            else:
                color = loop_c
            g.edge(
                f"L{int(r.Source)}", f"L{int(r.Target)}", label=f" {r.次數}",
                penwidth=f"{width:.2f}", color=color, fontcolor=color, fontsize="12",
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
    """題序流動圖：各組平均 Bloom Level 隨題序變化。"""
    if profile.empty:
        return _empty_fig(title)
    fig = px.line(
        profile, x="題序", y="平均Bloom", color="組別", markers=True,
        title=title, template=_TEMPLATE,
    )
    fig.update_yaxes(title="平均 Bloom Level")
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
    """題序 × Bloom Level 趨勢圖：散布點 + 每組迴歸線(含信賴區帶) + 高低階底色。

    points: 欄位 學生、組別、題序、Bloom。
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
            x=sub["題序"] + jitter, y=sub["Bloom"], mode="markers",
            name=f"{g}（提問）", legendgroup=g,
            marker=dict(color=_hex_to_rgba(c, 0.45), size=6),
            hovertemplate="題序%{x:.0f}<br>Bloom L%{y}<extra></extra>",
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
                      yaxis_title="Bloom Level", hovermode="closest")
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
) -> graphviz.Digraph:
    """GSEQ 顯著轉移網絡圖（六邊形固定位置，只畫達顯著的轉移、線上標 z 值）。

    仿標準滯後序列分析工具的「事件轉移圖」：
    - 節點：Bloom Level 圓圈（藍=低階、紅=高階），位置固定。
    - 只畫 |z|>1.96 的轉移；紅實線=顯著偏多、灰虛線=顯著偏少；線粗與標籤=調整殘差 z。
    """
    low_c, high_c = "#5DADE2", "#E74C3C"
    g = graphviz.Digraph(engine="neato")
    g.attr(bgcolor="white", outputorder="edgesfirst", overlap="false")
    g.attr("node", shape="circle", style="filled", fontcolor="white",
           fontsize="14", width="0.7", fixedsize="true", penwidth="0")

    positions = _ring_positions(levels)
    for lv in sorted(levels):
        x, y = positions[lv]
        fill = high_c if lv >= high_min else low_c
        g.node(f"L{lv}", label=f"L{lv}", pos=f"{x},{y}!", fillcolor=fill)

    sig = gseq_group[gseq_group["顯著"] != ""]
    if sig.empty:
        g.attr(label="（此組無達顯著的轉移）", labelloc="t", fontsize="14")
        return g

    max_z = max(float(abs(z)) for z in sig["調整殘差z"]) or 1.0
    for r in sig.itertuples():
        z = float(r.調整殘差z)
        width = 1.0 + 5.0 * (abs(z) / max_z)
        if z > 0:
            color, style = "#C0392B", "solid"   # 顯著偏多：紅實線
        else:
            color, style = "#95A5A6", "dashed"   # 顯著偏少：灰虛線
        g.edge(r.Source, r.Target, label=f" {z:.2f}", penwidth=f"{width:.2f}",
               color=color, fontcolor=color, style=style, fontsize="11")
    return g
