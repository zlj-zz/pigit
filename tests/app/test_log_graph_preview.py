# -*- coding: utf-8 -*-
"""
Module: tests/app/test_log_graph_preview.py
Description: Tests for the Branch-only git log --graph preview panel.
Author: Zev
Date: 2026-08-18
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from pigit.app_branch import BranchPanel
from pigit.app_log_graph_preview import LogGraphPreview
from pigit.git.model import Branch
from pigit.termui import EVT_SELECTION_CHANGED, Component
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.root import ComponentRoot
from pigit.termui.surface import Surface
from pigit.termui._color import _ANSI_16_PALETTE
from pigit.termui.event_bus import EventBus
from pigit.termui.reactive import Signal
from pigit.termui.widgets.text_browser import TextBrowser
from pigit.viewmodels.branch import IBranchViewModel


@pytest.fixture
def vm() -> Mock:
    mock = Mock(spec=IBranchViewModel)
    mock.items = Signal([])
    mock.load_log_graph.return_value = ["* abc feat", "* def main"]
    return mock


@pytest.fixture
def preview(vm: Mock) -> LogGraphPreview:
    return LogGraphPreview(vm=vm, id="log_graph_preview")


class _FakeTask:
    """Stand-in for AsyncTask with just the cancel() surface the preview uses."""

    def cancel(self) -> None:
        pass


def _run_sync(work, callback):
    """Run a background load inline so tests can assert its effect synchronously."""
    callback(work())
    return _FakeTask()


@pytest.fixture(autouse=True)
def _sync_async(monkeypatch):
    """Replace the real thread-pool runner with an inline one for determinism."""
    monkeypatch.setattr("pigit.app_log_graph_preview.run_async", _run_sync)


def _mount(bus: EventBus, preview: LogGraphPreview) -> ComponentRoot:
    root = ComponentRoot(preview, event_bus=bus)
    preview.mount()
    return root


def _branch_panel(vm: Mock, name: str = "feat") -> BranchPanel:
    panel = BranchPanel(get_git=lambda: Mock(bisect_status=Mock(return_value=None)), vm=vm)
    panel.branches = [Branch(name, "0", "0", False)]
    panel.curr_no = 0
    return panel


def test_loads_graph_for_branch_selection(preview: LogGraphPreview, vm: Mock) -> None:
    bus = EventBus()
    _mount(bus, preview)
    bus.publish(EVT_SELECTION_CHANGED, active=_branch_panel(vm, "feat"))
    vm.load_log_graph.assert_called_once_with("feat")
    assert preview._title == "feat"
    assert preview._browser.lines == ["* abc feat", "* def main"]


def test_clears_when_active_is_not_branch(preview: LogGraphPreview, vm: Mock) -> None:
    bus = EventBus()
    _mount(bus, preview)
    bus.publish(EVT_SELECTION_CHANGED, active=_branch_panel(vm, "feat"))
    bus.publish(EVT_SELECTION_CHANGED, active=Component())
    vm.load_log_graph.assert_called_once()
    assert preview._title == "Log"
    assert preview._browser.lines == []


def test_shows_placeholder_when_branch_has_no_commits(
    preview: LogGraphPreview, vm: Mock
) -> None:
    vm.load_log_graph.return_value = []
    bus = EventBus()
    _mount(bus, preview)
    bus.publish(EVT_SELECTION_CHANGED, active=_branch_panel(vm, "empty"))
    assert preview._browser.lines == ["No commits"]


def test_wheel_scrolls_graph(preview: LogGraphPreview) -> None:
    preview.resize((24, 10))
    preview.set_lines([f"* c{i}" for i in range(40)], title="feat")
    assert preview._browser.scroll_i == 0
    down = MouseEvent(2, 3, MouseButton.WHEEL_DOWN, MouseKind.PRESS)
    assert preview.handle_mouse(down) is True
    assert preview._browser.scroll_i == TextBrowser.WHEEL_SCROLL_LINES


def test_clears_when_branch_has_no_selection(
    preview: LogGraphPreview, vm: Mock
) -> None:
    bus = EventBus()
    _mount(bus, preview)
    panel = _branch_panel(vm, "feat")
    panel.branches = []
    bus.publish(EVT_SELECTION_CHANGED, active=panel)
    vm.load_log_graph.assert_not_called()
    assert preview._title == "Log"
    assert preview._browser.lines == []


def test_deactivate_unsubscribes(preview: LogGraphPreview, vm: Mock) -> None:
    bus = EventBus()
    _mount(bus, preview)
    bus.publish(EVT_SELECTION_CHANGED, active=_branch_panel(vm, "feat"))
    assert vm.load_log_graph.call_count == 1
    preview.unmount()
    bus.publish(EVT_SELECTION_CHANGED, active=_branch_panel(vm, "other"))
    assert vm.load_log_graph.call_count == 1


def test_graph_loads_when_branch_list_arrives(
    preview: LogGraphPreview, vm: Mock
) -> None:
    """Tab switch happens before async load_branches; preview must follow items."""
    bus = EventBus()
    root = ComponentRoot(preview, event_bus=bus)
    preview.mount()
    panel = BranchPanel(get_git=lambda: Mock(bisect_status=Mock(return_value=None)), vm=vm)
    panel.parent = root

    def _publish(action, **data):
        data.setdefault("active", panel)
        return bus.publish(action, **data)

    root._app_on_event = _publish
    panel.mount()

    bus.publish(EVT_SELECTION_CHANGED, active=panel)
    vm.load_log_graph.assert_not_called()
    assert preview._browser.lines == []

    vm.items.set([Branch("feat", "0", "0", False)])
    vm.load_log_graph.assert_called_once_with("feat")
    assert preview._title == "feat"
    assert preview._browser.lines == ["* abc feat", "* def main"]


def test_render_draws_title_and_graph_lines(preview: LogGraphPreview) -> None:
    preview.resize((24, 8))
    preview.set_lines(["* abc feat", "* def main"], title="feat")
    surface = Surface(24, 8)
    preview.paint(surface)
    rows = ["".join(c.char for c in row) for row in surface._rows]
    assert any("feat" in row for row in rows)
    assert any("* abc feat" in row for row in rows)


def test_render_applies_ansi_foreground(preview: LogGraphPreview) -> None:
    preview.resize((24, 8))
    preview.set_lines(["\x1b[32mHEAD\x1b[m"], title="feat")
    assert preview._browser.lines == ["HEAD"]
    surface = Surface(24, 8)
    preview.paint(surface)
    green = _ANSI_16_PALETTE[2]
    painted = [
        cell
        for row in surface._rows
        for cell in row
        if cell.char == "H" and cell.fg == green
    ]
    assert painted


def test_branch_jk_scrolls_preview(
    preview: LogGraphPreview, vm: Mock, monkeypatch
) -> None:
    preview.resize((24, 10))
    preview.set_lines([f"* c{i}" for i in range(40)], title="feat")
    preview.mount()
    monkeypatch.setattr("pigit.app_branch.by_id", lambda *_args, **_kwargs: preview)
    panel = _branch_panel(vm)
    panel._scroll_preview_down()
    assert preview._browser.scroll_i == LogGraphPreview.SCROLL_PAGE_SIZE
    panel._scroll_preview_up()
    assert preview._browser.scroll_i == 0


def test_jk_does_not_scroll_detached_preview(
    preview: LogGraphPreview, vm: Mock, monkeypatch
) -> None:
    """J/K is a no-op while the preview is detached (toggled off)."""
    preview.resize((24, 10))
    preview.set_lines([f"* c{i}" for i in range(40)], title="feat")
    monkeypatch.setattr("pigit.app_branch.by_id", lambda *_args, **_kwargs: preview)
    panel = _branch_panel(vm)
    panel._scroll_preview_down()
    panel._scroll_preview_up()
    assert preview._browser.scroll_i == 0


def test_stale_async_result_is_dropped(
    preview: LogGraphPreview, vm: Mock, monkeypatch
) -> None:
    """A load superseded by a newer selection is never applied."""
    captured: list[tuple] = []

    def _capture(work, callback):
        captured.append((work, callback))
        return _FakeTask()

    monkeypatch.setattr("pigit.app_log_graph_preview.run_async", _capture)
    bus = EventBus()
    _mount(bus, preview)

    bus.publish(EVT_SELECTION_CHANGED, active=_branch_panel(vm, "feat"))
    bus.publish(EVT_SELECTION_CHANGED, active=_branch_panel(vm, "main"))

    # Completing the stale "feat" load must not clobber the current selection.
    stale_work, stale_cb = captured[0]
    stale_cb(stale_work())
    assert preview._title == "Log"
    assert preview._browser.lines == []

    current_work, current_cb = captured[1]
    current_cb(current_work())
    assert preview._title == "main"
    assert preview._browser.lines == ["* abc feat", "* def main"]


def test_render_truncates_graph_line_before_border(preview: LogGraphPreview) -> None:
    """Long graph lines are clipped so the right frame border stays intact."""
    preview.resize((20, 8))
    long_line = "* abc " + "x" * 60
    preview.set_lines([long_line], title="feat")
    surface = Surface(20, 8)
    preview.paint(surface)
    rows = ["".join(c.char for c in row) for row in surface._rows]
    # First content row (index 1) holds the line clipped to the inner width (18).
    assert "x" * 12 in rows[1]
    assert "x" * 13 not in rows[1]
    # The right border column (index 19) is preserved on every content row.
    for row in rows[1:-1]:
        assert row[19] == "│", f"border overwritten: {row[19]!r}"


def test_set_vm_cancels_inflight_load_and_clears_request() -> None:
    """set_vm drops a pending graph load so stale content cannot land."""
    from unittest.mock import Mock

    panel = LogGraphPreview(vm=Mock())
    task = Mock()
    panel._load_task = task
    panel._requested_branch = "stale"
    panel.set_vm(Mock())
    task.cancel.assert_called_once()
    assert panel._load_task is None
    assert panel._requested_branch is None
