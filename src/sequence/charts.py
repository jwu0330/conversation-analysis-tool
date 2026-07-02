"""序列分析專用圖表（Plotly，獨立於 src/core/charts）。"""
from __future__ import annotations

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


def transition_dot(trans_group: pd.DataFrame, high_min: int = 4) -> str:
    """產生 Graphviz DOT 字串：節點=Bloom Level 圓圈，箭頭=轉移。

    - 箭頭粗細 = 該轉移出現次數（相對最大值縮放）
    - 支援自我迴圈（例如 L2→L2，代表連續同層級提問）
    - 箭頭顏色：往高階=綠、往低階=橘、同層級=灰，直觀看出「低轉高」
    以 st.graphviz_chart(dot) 顯示，前端渲染，不需安裝 Graphviz 主程式。
    """
    if trans_group.empty:
        return 'digraph { label="資料不足，無法繪圖"; labelloc="t"; }'

    levels = sorted(set(trans_group["Source"]) | set(trans_group["Target"]))
    max_count = max(int(trans_group["次數"].max()), 1)

    lines = [
        "digraph {",
        "  rankdir=LR;",
        '  bgcolor="white";',
        '  node [shape=circle, style=filled, fontcolor=white, '
        'fontsize=14, width=0.65, fixedsize=true];',
        "  edge [fontsize=11];",
    ]
    for lv in levels:
        color = _LEVEL_COLOR.get(int(lv), "#7F8C8D")
        lines.append(f'  L{lv} [label="L{lv}", fillcolor="{color}"];')
    for r in trans_group.itertuples():
        width = 1.0 + 6.0 * (r.次數 / max_count)
        if r.Target > r.Source:
            edge_color = "#27AE60"      # 往高階：綠
        elif r.Target < r.Source:
            edge_color = "#E67E22"      # 往低階：橘
        else:
            edge_color = "#95A5A6"      # 同層級：灰
        lines.append(
            f'  L{r.Source} -> L{r.Target} '
            f'[penwidth={width:.2f}, label="{r.次數}", color="{edge_color}"];'
        )
    lines.append("}")
    return "\n".join(lines)


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
