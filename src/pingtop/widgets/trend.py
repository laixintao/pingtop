from __future__ import annotations

import math
from collections.abc import Sequence

from rich.text import Text

from pingtop.models import TIMEOUT_MARKER, TREND_BLOCKS, trend_cells

TREND_STYLES = (
    "#86efac",
    "#4ade80",
    "#a3e635",
    "#fde047",
    "#fb923c",
    "#f87171",
    "#ef4444",
    "#dc2626",
)
TIMEOUT_STYLE = "bold #ef4444"
DETAIL_GRAPH_EMPTY_STYLE = "#4b5563"
DETAIL_GRAPH_AXIS_STYLE = "#9ca3af"


def render_trend(history: Sequence[float | None] | None, *, width: int | None = None) -> Text:
    if not history:
        return Text("-")
    trend = Text()
    cells = trend_cells(list(history))
    if width is not None and width > 0:
        cells = cells[-width:]
    for block, bucket in cells:
        style = TIMEOUT_STYLE if bucket is None else TREND_STYLES[bucket]
        trend.append(block, style=style)
    return trend


def render_trend_legend() -> Text:
    legend = Text()
    legend.append("Trend Legend\n")
    legend.append("low RTT ")
    for block, style in zip(TREND_BLOCKS, TREND_STYLES, strict=True):
        legend.append(f" {block} ", style=style)
    legend.append(" high RTT\n")
    legend.append("timeout ")
    legend.append(f" {TIMEOUT_MARKER} ", style=TIMEOUT_STYLE)
    return legend


def render_trend_graph(
    history: Sequence[float | None] | None,
    *,
    width: int | None = None,
    height: int = 4,
) -> Text:
    if not history:
        return Text("-")
    cells = trend_cells(list(history))
    if width is not None and width > 0:
        cells = cells[-width:]

    graph = Text()
    total_buckets = len(TREND_STYLES)
    for level in range(height, 0, -1):
        if graph:
            graph.append("\n")
        for _, bucket in cells:
            if bucket is None:
                graph.append(TIMEOUT_MARKER, style=TIMEOUT_STYLE)
                continue
            bucket_height = max(1, math.ceil(((bucket + 1) / total_buckets) * height))
            if bucket_height >= level:
                graph.append("█", style=TREND_STYLES[bucket])
            else:
                graph.append("·", style=DETAIL_GRAPH_EMPTY_STYLE)
    return graph


def render_detailed_trend_graph(
    history: Sequence[float | None] | None,
    *,
    width: int | None = None,
    height: int = 6,
) -> list[Text]:
    header = Text("RTT Graph", style="bold")
    if not history:
        return [header, Text("waiting for samples", style=DETAIL_GRAPH_EMPTY_STYLE)]

    cells = list(history)
    if width is not None and width > 0:
        cells = cells[-width:]
    if not cells:
        return [header, Text("waiting for samples", style=DETAIL_GRAPH_EMPTY_STYLE)]

    samples = [sample for sample in cells if sample is not None]
    if not samples:
        timeout_line = Text("timeouts │ ", style=DETAIL_GRAPH_AXIS_STYLE)
        timeout_line.append(TIMEOUT_MARKER * len(cells), style=TIMEOUT_STYLE)
        return [
            header,
            timeout_line,
            _render_graph_axis(len(cells), len("timeouts")),
            Text(" " * (len("timeouts") + 3) + "oldest -> newest", style=DETAIL_GRAPH_AXIS_STYLE),
        ]

    low = min(samples)
    high = max(samples)
    span = max(high - low, 1.0)
    label_width = max(len(f"{low:.1f}"), len(f"{high:.1f}"))

    effective_width = width if width is not None else len(cells)
    lines = [header]
    for level in range(height, 0, -1):
        scale_value = low + (span * (level - 1) / max(height - 1, 1))
        line = Text(f"{scale_value:>{label_width}.1f} │ ", style=DETAIL_GRAPH_AXIS_STYLE)
        for sample in cells:
            if sample is None:
                line.append(TIMEOUT_MARKER, style=TIMEOUT_STYLE)
                continue
            sample_height = 1 + round(((sample - low) / span) * (height - 1))
            bucket = min(
                len(TREND_STYLES) - 1,
                int(((sample - low) / span) * (len(TREND_STYLES) - 1)),
            )
            if sample_height >= level:
                line.append("█", style=TREND_STYLES[bucket])
            else:
                line.append("·", style=DETAIL_GRAPH_EMPTY_STYLE)
        for _ in range(effective_width - len(cells)):
            line.append("·", style=DETAIL_GRAPH_EMPTY_STYLE)
        lines.append(line)

    lines.append(_render_graph_axis(effective_width, label_width))
    return lines


def _render_graph_axis(width: int, label_width: int) -> Text:
    axis = Text(" " * label_width, style=DETAIL_GRAPH_AXIS_STYLE)
    axis.append(" └", style=DETAIL_GRAPH_AXIS_STYLE)
    axis.append("─" * width, style=DETAIL_GRAPH_AXIS_STYLE)
    return axis
