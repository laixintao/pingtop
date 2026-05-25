from __future__ import annotations

from typing import cast

from rich.text import Text
from textual.widgets import Static

import pingtop.models
from pingtop.widgets.trend import render_detailed_trend_graph


class DetailsPanel(Static):
    DEFAULT_MESSAGE = "Select a host to inspect live statistics."
    COLUMN_GAP = 4
    LEFT_COLUMN_MAX_WIDTH = 30

    def show_host(self, row: dict[str, object] | None) -> None:
        if row is None:
            self.update(self.DEFAULT_MESSAGE)
            return
        history = cast(list[float | None], row["history_ms"])
        left_lines = self._left_column_lines(row)
        left_width = self._left_column_width(left_lines)
        graph_width = self._graph_width(left_width)
        right_lines = render_detailed_trend_graph(history, width=graph_width)
        self.update(self._compose_columns(left_lines, right_lines, left_width))

    @staticmethod
    def _fmt(value: object) -> str:
        if value is None:
            return "-"
        return f"{float(cast(float, value)):.1f} ms"

    def _graph_width(self, left_width: int) -> int:
        if self.size.width <= 0:
            return 32
        available = self.size.width - left_width - self.COLUMN_GAP - 8
        return max(16, min(pingtop.models.MAX_HISTORY, available))

    def _left_column_lines(self, row: dict[str, object]) -> list[str]:
        lines = [
            f"Host: {row['target']}",
            f"IP: {row['resolved_ip'] or '-'}",
            f"State: {row['state']}",
            f"Last RTT: {self._fmt(row['last_rtt_ms'])}",
            f"Min RTT: {self._fmt(row['min_rtt_ms'])}",
            f"Avg RTT: {self._fmt(row['avg_rtt_ms'])}",
            f"Max RTT: {self._fmt(row['max_rtt_ms'])}",
            f"StdDev: {self._fmt(row['stddev_ms'])}",
            f"Sent: {row['seq']}",
            f"Loss: {row['lost']} ({float(cast(float, row['loss_percent'])):.1f}%)",
        ]

        last_err = row.get('last_error')
        if last_err not in (None, '', b''):
            lines.append(f"Error: {self._truncate(str(last_err))}")

        return lines

    def _left_column_width(self, lines: list[str]) -> int:
        if not lines:
            return 0
        return min(self.LEFT_COLUMN_MAX_WIDTH, max(len(line) for line in lines))

    def _compose_columns(
        self, left_lines: list[str], right_lines: list[Text], left_width: int
    ) -> Text:
        details = Text()
        line_count = max(len(left_lines), len(right_lines))
        for index in range(line_count):
            if index:
                details.append("\n")
            left_line = left_lines[index] if index < len(left_lines) else ""
            details.append(self._truncate(left_line, left_width).ljust(left_width))
            details.append(" " * self.COLUMN_GAP)
            if index < len(right_lines):
                details.append_text(right_lines[index])
        return details

    @staticmethod
    def _truncate(value: str, width: int | None = None) -> str:
        if width is None or width <= 0 or len(value) <= width:
            return value
        if width <= 3:
            return value[:width]
        return f"{value[: width - 3]}..."
