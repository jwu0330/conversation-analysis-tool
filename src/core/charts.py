"""互動式圖表（Plotly）。回傳 Figure，由 UI 負責顯示與下載。"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

_TEMPLATE = "plotly_white"


def bar_chart(
    data: pd.DataFrame, x: str, y: str, color: str | None = None, title: str = ""
) -> go.Figure:
    """群組長條圖（color 用於分組並排）。"""
    fig = px.bar(
        data, x=x, y=y, color=color, barmode="group", title=title, template=_TEMPLATE
    )
    fig.update_layout(legend_title_text=color or "")
    return fig


def stacked_bar_chart(
    data: pd.DataFrame, x: str, y: str, color: str, title: str = ""
) -> go.Figure:
    """堆疊長條圖。"""
    fig = px.bar(
        data, x=x, y=y, color=color, barmode="stack", title=title, template=_TEMPLATE
    )
    fig.update_layout(legend_title_text=color)
    return fig


def heatmap(matrix: pd.DataFrame, title: str = "") -> go.Figure:
    """交叉表熱圖（matrix 為 index×columns 的數值表）。"""
    fig = px.imshow(
        matrix,
        text_auto=True,
        aspect="auto",
        color_continuous_scale="Blues",
        title=title,
    )
    fig.update_layout(template=_TEMPLATE)
    return fig


def pie_chart(data: pd.DataFrame, names: str, values: str, title: str = "") -> go.Figure:
    fig = px.pie(data, names=names, values=values, title=title, template=_TEMPLATE)
    return fig


def line_chart(
    data: pd.DataFrame, x: str, y: str, color: str | None = None, title: str = ""
) -> go.Figure:
    fig = px.line(
        data, x=x, y=y, color=color, markers=True, title=title, template=_TEMPLATE
    )
    return fig


def box_plot(
    data: pd.DataFrame, x: str, y: str, color: str | None = None, title: str = ""
) -> go.Figure:
    fig = px.box(data, x=x, y=y, color=color, title=title, template=_TEMPLATE)
    return fig
