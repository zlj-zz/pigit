# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_overlay_api.py
Description: Tests for overlay and convenience APIs.
Author: Zev
Date: 2026-06-10
"""

from __future__ import annotations

import threading
import time

import pytest
from unittest.mock import MagicMock, patch

from pigit.termui._layer import LayerKind
from pigit.termui.types import ToastPosition
from pigit.termui._runtime_context import (
    RuntimeContext,
    _runtime_ctx,
    set_overlay_host,
)
from pigit.termui.async_task import AsyncTask
from pigit.termui.overlay import (
    dismiss_sheet,
    dismiss_toast,
    exec_external,
    get_badge,
    get_badge_signal,
    hide_spinner,
    run_with_spinner,
    show_badge,
    show_sheet,
    show_spinner,
    show_toast,
)


@pytest.fixture(autouse=True)
def _clear_runtime_context():
    """Reset _runtime_ctx to default before each test."""
    token = _runtime_ctx.set(None)
    yield
    try:
        _runtime_ctx.reset(token)
    except Exception:
        pass


class TestOverlayHelpers:
    def _make_host(self):
        host = MagicMock()
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = None
        host._size = (80, 24)
        return host

    def test_show_toast(self):
        from pigit.termui.widgets import Toast

        from pigit.termui._runtime_context import set_overlay_host

        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = self._make_host()
        set_overlay_host(host)
        result = show_toast("hello", duration=1.0)
        host._layer_stack.push.assert_called_once()
        call = host._layer_stack.push.call_args
        assert call.args[0] is LayerKind.TOAST
        assert isinstance(call.args[1], Toast)
        assert call.args[1].message == "hello"
        assert call.args[1].duration == 1.0
        assert result is call.args[1]

    def test_show_toast_no_host(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        assert show_toast("hello") is None

    def test_show_sheet(self):
        from pigit.termui._runtime_context import set_overlay_host

        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = self._make_host()
        set_overlay_host(host)
        child = MagicMock()
        result = show_sheet(child, height=4)
        host.show_sheet.assert_called_once_with(
            child,
            4,
            max_fraction=1 / 3,
            show_edge_rule=True,
            title_core=None,
            title_align="right",
            edge="bottom",
            bg=None,
            edge_fg=None,
        )
        assert result is host.show_sheet.return_value

    def test_show_sheet_top_edge(self):
        from pigit.termui._runtime_context import set_overlay_host

        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = self._make_host()
        set_overlay_host(host)
        child = MagicMock()
        result = show_sheet(child, height=4, edge="top")
        host.show_sheet.assert_called_once_with(
            child,
            4,
            max_fraction=1 / 3,
            show_edge_rule=True,
            title_core=None,
            title_align="right",
            edge="top",
            bg=None,
            edge_fg=None,
        )
        assert result is host.show_sheet.return_value

    def test_show_sheet_bg_none(self):
        from pigit.termui._runtime_context import set_overlay_host

        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = self._make_host()
        set_overlay_host(host)
        child = MagicMock()
        show_sheet(child, height=4, edge="top", bg=None)
        host.show_sheet.assert_called_once_with(
            child,
            4,
            max_fraction=1 / 3,
            show_edge_rule=True,
            title_core=None,
            title_align="right",
            edge="top",
            bg=None,
            edge_fg=None,
        )

    def test_dismiss_sheet(self):
        from pigit.termui._runtime_context import set_overlay_host

        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = self._make_host()
        set_overlay_host(host)
        dismiss_sheet()
        host.dismiss_sheet.assert_called_once()

    def test_show_badge(self):
        from pigit.termui._runtime_context import set_overlay_host

        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = self._make_host()
        host.badge_text = "old"
        set_overlay_host(host)
        show_badge("new")
        host.show_badge.assert_called_once_with("new", duration=None, bg=None, fg=None)

    def test_get_badge_no_host(self):
        assert get_badge() == (None, None, None)

    def test_get_badge_with_host(self):
        from pigit.termui._runtime_context import set_overlay_host

        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = self._make_host()
        host.badge_text = "txt"
        host.badge_bg = (1, 2, 3)
        host.badge_fg = (4, 5, 6)
        set_overlay_host(host)
        assert get_badge() == ("txt", (1, 2, 3), (4, 5, 6))

    def test_show_spinner(self):
        from pigit.termui.widgets import Toast

        from pigit.termui._runtime_context import set_overlay_host

        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = self._make_host()
        set_overlay_host(host)
        toast = show_spinner("loading")
        host._layer_stack.push.assert_called_once()
        call = host._layer_stack.push.call_args
        assert isinstance(call.args[1], Toast)
        assert call.args[1].duration == 3600.0
        assert call.args[1]._position == ToastPosition.BOTTOM_LEFT
        assert call.args[1]._spin is True
        assert any("loading" in s.text for s in call.args[1]._segments)
        centered = show_spinner("x", position=ToastPosition.CENTER)
        assert centered is not None
        assert centered._position == ToastPosition.CENTER

    def test_dismiss_toast(self):
        from pigit.termui._runtime_context import set_overlay_host

        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = self._make_host()
        existing_toast = MagicMock()
        host._layer_stack.top.return_value = existing_toast
        set_overlay_host(host)
        dismiss_toast()
        existing_toast.hide.assert_called_once()
        host._layer_stack.pop.assert_called_once_with(LayerKind.TOAST)

    def test_hide_spinner(self):
        from pigit.termui._runtime_context import set_overlay_host

        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = self._make_host()
        existing_toast = MagicMock()
        host._layer_stack.top.return_value = existing_toast
        set_overlay_host(host)
        hide_spinner()
        existing_toast.hide.assert_called_once()
        host._layer_stack.pop.assert_called_once_with(LayerKind.TOAST)


class TestExecExternal:
    def test_raises_when_no_session(self):
        with pytest.raises(RuntimeError, match="No active TUI session"):
            exec_external(["echo", "hi"])

    def test_runs_command_and_restores_session(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        session = MagicMock()
        runtime.session = session
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            result = exec_external(["echo", "hi"])
            mock_run.assert_called_once_with(
                ["echo", "hi"], cwd=None, env=None, stdin=None, stdout=None, stderr=None
            )
            session.suspend.assert_called_once()
            session.resume.assert_called_once()
            assert result is mock_run.return_value

    def test_resume_failure_is_logged_and_raised(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        session = MagicMock()
        session.resume.side_effect = RuntimeError("boom")
        runtime.session = session
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            with pytest.raises(RuntimeError, match="boom"):
                exec_external(["echo", "hi"])

    def test_stops_keyboard_reader_while_external_owns_tty(self):
        """KeyboardInput must not read stdin while nvim queries DSR/OSC 11."""
        from pigit.termui._runtime_context import set_overlay_host

        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        session = MagicMock()
        runtime.session = session

        input_handle = MagicMock()
        loop = MagicMock()
        loop._input_handle = input_handle
        host = MagicMock()
        host._event_loop = loop
        set_overlay_host(host)

        order: list[str] = []
        input_handle.stop.side_effect = lambda: order.append("stop")
        session.suspend.side_effect = lambda: order.append("suspend")
        session.resume.side_effect = lambda: order.append("resume")
        input_handle.start.side_effect = lambda: order.append("start")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = lambda *a, **k: order.append("run") or MagicMock()
            exec_external(["nvim", "file"])

        assert order == ["stop", "suspend", "run", "resume", "start"]


class _FakeLoop:
    """Interval scheduler for tests, without a running event loop."""

    def __init__(self) -> None:
        self._next_id = 0
        self.timers: dict[int, object] = {}

    def add_interval(self, interval, callback):
        self._next_id += 1
        self.timers[self._next_id] = callback
        return self._next_id

    def remove_interval(self, tid: int) -> None:
        self.timers.pop(tid, None)

    def fire(self) -> None:
        """Run every armed timer once, as the event loop would."""
        for callback in list(self.timers.values()):
            callback()


def _host_with(loop: _FakeLoop):
    runtime = RuntimeContext()
    _runtime_ctx.set(runtime)
    host = MagicMock()
    host._event_loop = loop
    set_overlay_host(host)
    return host


def _drain_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not predicate():
        AsyncTask.poll_all()
        time.sleep(0.005)


class TestSpinnerDelay:
    """A spinner belongs to work that takes long enough to need one."""

    def test_fast_work_never_shows_a_spinner(self, mocker) -> None:
        spinner = mocker.patch("pigit.termui.overlay.show_spinner")
        hidden = mocker.patch("pigit.termui.overlay.hide_spinner")
        loop = _FakeLoop()
        _host_with(loop)
        finished: list[int] = []

        run_with_spinner(lambda: 1, finished.append, label="Staging")
        _drain_until(lambda: finished)

        assert finished == [1]
        assert spinner.call_count == 0
        assert hidden.call_count == 0
        assert loop.timers == {}  # the armed timer was cancelled, not left to fire

    def test_slow_work_shows_the_spinner_then_dismisses_it(self, mocker) -> None:
        spinner = mocker.patch("pigit.termui.overlay.show_spinner")
        hidden = mocker.patch("pigit.termui.overlay.hide_spinner")
        loop = _FakeLoop()
        _host_with(loop)
        gate = threading.Event()
        finished: list[str] = []

        def work() -> str:
            gate.wait(2.0)
            return "done"

        run_with_spinner(work, finished.append, label="Staging")
        loop.fire()  # the delay elapsed while the work runs on
        assert spinner.call_count == 1
        assert hidden.call_count == 0

        gate.set()
        _drain_until(lambda: finished)

        assert finished == ["done"]
        assert hidden.call_count == 1

    def test_a_failed_worker_never_arms_the_spinner(self, mocker) -> None:
        """The failure toast owns the toast slot; a timer armed before the
        failure would fire over it and stay there for an hour."""
        spinner = mocker.patch("pigit.termui.overlay.show_spinner")
        toast = mocker.patch("pigit.termui.overlay.show_toast")
        loop = _FakeLoop()
        _host_with(loop)
        finished: list[str] = []

        def work() -> str:
            raise RuntimeError("index locked")

        run_with_spinner(work, finished.append, label="Staging")
        _drain_until(lambda: toast.called)

        loop.fire()

        assert finished == []
        assert spinner.call_count == 0
        assert loop.timers == {}
