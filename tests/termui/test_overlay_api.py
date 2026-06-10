# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_overlay_api.py
Description: Tests for overlay and convenience APIs.
Author: Zev
Date: 2026-06-10
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from pigit.termui._layer import LayerKind
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx
from pigit.termui._overlay_api import (
    dismiss_sheet,
    dismiss_toast,
    exec_external,
    get_badge,
    get_badge_signal,
    hide_spinner,
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
        host.show_sheet.assert_called_once_with(child, 4, show_border=False)
        assert result is host.show_sheet.return_value

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
        show_spinner("loading")
        host._layer_stack.push.assert_called_once()
        call = host._layer_stack.push.call_args
        assert isinstance(call.args[1], Toast)
        assert call.args[1].duration == 3600.0
        assert any("loading" in s.text for s in call.args[1]._segments)

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
        from pigit.termui._runtime_context import set_session

        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        session = MagicMock()
        set_session(session)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            result = exec_external(["echo", "hi"])
            mock_run.assert_called_once_with(
                ["echo", "hi"], cwd=None, stdin=None, stdout=None, stderr=None
            )
            session.suspend.assert_called_once()
            session.resume.assert_called_once()
            assert result is mock_run.return_value

    def test_resume_failure_is_logged_and_raised(self):
        from pigit.termui._runtime_context import set_session

        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        session = MagicMock()
        session.resume.side_effect = RuntimeError("boom")
        set_session(session)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            with pytest.raises(RuntimeError, match="boom"):
                exec_external(["echo", "hi"])
