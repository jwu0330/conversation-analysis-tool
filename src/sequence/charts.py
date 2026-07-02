"""序列分析專用圖表（Plotly，獨立於 src/core/charts）。"""
from __future__ import annotations

import math

import graphviz
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
