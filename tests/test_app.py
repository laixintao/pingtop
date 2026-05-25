from __future__ import annotations

from collections import defaultdict

import pytest
from rich.text import Text
from textual.widgets import Static

from pingtop.app import PingTopApp
from pingtop.models import PingResult, SessionConfig, SortKey
from pingtop.session import PingSession
from pingtop.widgets.details_panel import DetailsPanel
from pingtop.widgets.host_table import HostTable


class FakeEngine:
    def __init__(self) -> None:
        self._counts: defaultdict[str, int] = defaultdict(int)

    async def ping_once(
        self, target: str, timeout: float, packet_size: int, flag: int
    ) -> PingResult:
        self._counts[target] += 1
        count = self._counts[target]
        if target == "bad-host":
            return PingResult(success=False, error_message="Unknown host")
        if count % 3 == 0:
            return PingResult(success=False, resolved_ip="127.0.0.1")
        return PingResult(success=True, rtt_ms=10.0 + count, resolved_ip="127.0.0.1")


class FakeTable:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def scroll_to(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


@pytest.mark.asyncio
async def test_app_boots_and_updates_rows() -> None:
    session = PingSession(SessionConfig(interval=0.05, timeout=0.01), ["1.1.1.1"])
    app = PingTopApp(session=session, engine=FakeEngine())

    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause(0.25)
        table = app.query_one(HostTable)
        row = session.host_snapshot(next(iter(session.hosts)))
        assert row["seq"] >= 1  # type: ignore[operator]
        assert row["trend"]
        trend_index = HostTable.COLUMN_PROFILES["wide"].index("trend")
        trend_cell = table.get_row(str(row["id"]))[trend_index]
        assert isinstance(trend_cell, Text)
        assert trend_cell.spans
        assert str(table.ordered_columns[-1].key.value) == "trend"
        assert table.ordered_columns[-1].width > 20
        await pilot.press("q")


@pytest.mark.asyncio
async def test_app_host_lifecycle_actions() -> None:
    session = PingSession(SessionConfig(interval=0.05, timeout=0.01), ["1.1.1.1"])
    app = PingTopApp(session=session, engine=FakeEngine())

    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        app._handle_add_host("8.8.8.8")
        await pilot.pause(0.1)
        assert len(session.hosts) == 2

        selected = session.selected_host_id
        assert selected is not None
        app._handle_edit_host(selected, "9.9.9.9")
        assert session.hosts[selected].config.target == "9.9.9.9"

        app.action_toggle_selected_pause()
        assert session.hosts[selected].paused is True

        app.action_toggle_selected_pause()
        assert session.hosts[selected].paused is False

        app.action_reset_selected()
        assert session.hosts[selected].stats.seq == 0

        app._handle_delete_host(selected, True)
        assert selected not in session.hosts
        await pilot.press("q")


@pytest.mark.asyncio
async def test_app_sort_and_help_screen() -> None:
    session = PingSession(SessionConfig(interval=0.05, timeout=0.01), ["1.1.1.1", "bad-host"])
    app = PingTopApp(session=session, engine=FakeEngine())

    async with app.run_test() as pilot:
        await pilot.pause(0.15)
        await pilot.press("S")
        await pilot.pause(0.05)
        assert session.sort_key.value == "seq"
        assert session.sort_reverse is False
        await pilot.press("S")
        await pilot.pause(0.05)
        assert session.sort_reverse is True
        await pilot.press("h")
        await pilot.pause(0.05)
        assert app.screen_stack
        help_screen = app.screen_stack[-1]
        legend = help_screen.query_one("#trend-legend", Static)
        legend_render = legend.render()
        assert isinstance(legend_render, Text)
        assert "Trend Legend" in legend_render.plain
        assert "low RTT" in legend_render.plain
        assert "high RTT" in legend_render.plain
        await pilot.press("h")
        await pilot.pause(0.05)
        table = app.query_one(HostTable)
        assert table.row_count == len(session.hosts)
        await pilot.press("q")


@pytest.mark.asyncio
async def test_table_keeps_numeric_width_and_shows_sort_indicator() -> None:
    session = PingSession(SessionConfig(interval=0.05, timeout=0.01), ["1.1.1.1"])
    app = PingTopApp(session=session, engine=FakeEngine())

    async with app.run_test(size=(160, 40)) as pilot:
        table = app.query_one(HostTable)
        session.set_sort(session.sort_key, reverse=False)
        app._sync_all_rows()

        row = session.host_snapshot(next(iter(session.hosts)))
        row["seq"] = 318
        table.upsert_host(row)
        wide_value = table.get_row(str(row["id"]))[2]

        row["seq"] = 99
        table.upsert_host(row)
        narrow_value = table.get_row(str(row["id"]))[2]

        host_header = str(table.ordered_columns[0].label)
        assert host_header.endswith("▲")
        assert len(str(wide_value)) == len(str(narrow_value))
        assert str(narrow_value).strip() == "99"
        await pilot.press("q")


@pytest.mark.asyncio
async def test_details_panel_defaults_open_on_large_window_and_closed_on_small_window() -> None:
    large_session = PingSession(SessionConfig(interval=0.05, timeout=0.01), ["1.1.1.1"])
    large_app = PingTopApp(session=large_session, engine=FakeEngine())
    async with large_app.run_test(size=(160, 40)) as pilot:
        details = large_app.query_one(DetailsPanel)
        table = large_app.query_one(HostTable)
        assert details.has_class("hidden-panel")
        assert len(table.ordered_columns) == len(HostTable.COLUMN_PROFILES["wide"])
        await pilot.press("q")

    small_session = PingSession(SessionConfig(interval=0.05, timeout=0.01), ["1.1.1.1"])
    small_app = PingTopApp(session=small_session, engine=FakeEngine())
    async with small_app.run_test(size=(90, 24)) as pilot:
        details = small_app.query_one(DetailsPanel)
        table = small_app.query_one(HostTable)
        assert details.has_class("hidden-panel")
        assert len(table.ordered_columns) == len(HostTable.COLUMN_PROFILES["narrow"])
        await pilot.press("i")
        await pilot.pause(0.15)
        assert not details.has_class("hidden-panel")
        details_render = details.render()
        assert isinstance(details_render, Text)
        assert "RTT Graph" in details_render.plain
        assert "oldest -> newest" in details_render.plain
        assert "Host:" in details_render.plain
        await pilot.press("q")


@pytest.mark.asyncio
async def test_sync_rows_preserves_scroll_position() -> None:
    hosts = [f"10.0.0.{index}" for index in range(1, 41)]
    session = PingSession(SessionConfig(interval=0.05, timeout=0.01), hosts)
    app = PingTopApp(session=session, engine=FakeEngine())

    async with app.run_test(size=(90, 12)) as pilot:
        table = app.query_one(HostTable)
        await pilot.pause(0.1)
        table.scroll_to(y=8, immediate=True)
        await pilot.pause(0.05)
        before = table.scroll_y

        session.set_sort(SortKey.SEQ, reverse=False)
        total_hosts = len(session.hosts)
        for index, record in enumerate(session.hosts.values(), start=1):
            record.stats.seq = total_hosts - index
        app._sync_all_rows()
        await pilot.pause(0.05)

        assert before > 0
        assert table.scroll_y == pytest.approx(before, abs=1.0)
        await pilot.press("q")


@pytest.mark.asyncio
async def test_table_reserves_space_for_vertical_scrollbar_without_horizontal_scroll() -> None:
    hosts = [f"10.0.0.{index}" for index in range(1, 260)]
    session = PingSession(SessionConfig(interval=0.05, timeout=0.01), hosts)
    app = PingTopApp(session=session, engine=FakeEngine())

    async with app.run_test(size=(160, 12)) as pilot:
        table = app.query_one(HostTable)
        await pilot.pause(0.15)

        assert table.max_scroll_y > 0
        assert table.max_scroll_x == 0
        assert not table.show_horizontal_scrollbar
        await pilot.press("q")


def test_restore_table_viewport_coalesces_after_refresh_callbacks() -> None:
    session = PingSession(SessionConfig(), ["1.1.1.1"])
    app = PingTopApp(session=session, engine=FakeEngine())
    app.table = FakeTable()  # type: ignore[assignment]
    scheduled: list[object] = []

    def fake_call_after_refresh(callback: object, *args: object, **kwargs: object) -> bool:
        scheduled.append(callback)
        return True

    app.call_after_refresh = fake_call_after_refresh  # type: ignore[method-assign]

    app._restore_table_viewport(1.0, 2.0)
    app._restore_table_viewport(3.0, 4.0)

    assert len(scheduled) == 1
    assert len(app.table.calls) == 2  # type: ignore[attr-defined]

    app._flush_table_viewport_restore()

    assert app.table.calls[-1] == {  # type: ignore[attr-defined]
        "x": 3.0,
        "y": 4.0,
        "immediate": True,
        "force": True,
    }
