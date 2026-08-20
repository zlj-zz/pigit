# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_application.py
Description: Tests for pigit.termui.application.
Author: Zev
Date: 2026-04-17
"""

from unittest.mock import MagicMock, patch

import pytest

from pigit.termui import bind_action
from pigit.termui.application import Application
from pigit.termui.component import Component
from pigit.termui.event_loop import ExitEventLoop


class DummyRoot(Component):
    NAME = "dummy"

    def _render_surface(self, surface):
        pass

    def refresh(self):
        pass


class DummyApp(Application):
    def build_root(self):
        return DummyRoot()


class TestApplication:
    def test_run_uses_app_event_loop(self):
        app = DummyApp()
        with patch("pigit.termui.application.AppEventLoop") as MockLoop:
            mock_loop = MagicMock()
            MockLoop.return_value = mock_loop
            app.run()
            MockLoop.assert_called_once()
            mock_loop.run.assert_called_once()
            root = MockLoop.call_args.args[0]
            assert root.body.__class__ is DummyRoot

    def test_run_installs_bindings_and_handle_key_on_root(self):
        class _App(DummyApp):
            BINDINGS = [("x", "do_x")]

            def do_x(self):
                pass

            def handle_key(self, key):
                return False

        app = _App()
        with patch("pigit.termui.application.AppEventLoop") as MockLoop:
            MockLoop.return_value = MagicMock()
            app.run()
            root = MockLoop.call_args.args[0]
            assert "x" in root._key_handlers
            assert root._root_handle_key is not None
            kwargs = MockLoop.call_args.kwargs
            assert callable(kwargs.get("on_after_start"))
            assert kwargs.get("on_before_resize") == app.resize

    def test_after_start_hook_called(self):
        class Hooked(DummyApp):
            def after_start(self):
                self.hooked = True

        app = Hooked()
        with patch("pigit.termui.application.AppEventLoop") as MockLoop:
            MockLoop.return_value = MagicMock()
            app.run()
            MockLoop.call_args.kwargs["on_after_start"]()
            assert app.hooked is True

    def test_destroy_called_after_loop_exit(self):
        """root.destroy() must be called in finally block after loop exits."""
        app = DummyApp()
        with patch("pigit.termui.application.AppEventLoop") as MockLoop:
            MockLoop.return_value = MagicMock()
            app.run()
            assert app._root is None

    def test_get_help_groups_default_global(self):
        class _App(DummyApp):
            @bind_action("help", "?", desc="Toggle help")
            def help(self):
                pass

        app = _App()
        groups = app.get_help_groups()
        assert len(groups) == 1
        assert groups[0][0] == "Global"
        assert groups[0][1]

    def test_get_help_groups_empty_when_no_bindings(self):
        app = DummyApp()
        assert app.get_help_groups() == []

    def test_min_terminal_size_quits_after_after_start(self):
        class SizedApp(DummyApp):
            min_terminal_size = (65, 10)

        app = SizedApp()
        with patch("pigit.termui.application.AppEventLoop") as MockLoop:
            MockLoop.return_value = MagicMock()
            app.run()
            on_after_start = MockLoop.call_args.kwargs["on_after_start"]
            with patch("pigit.termui.tty_io.terminal_size", return_value=(64, 10)):
                with pytest.raises(ExitEventLoop) as exc_info:
                    on_after_start()
                assert (
                    exc_info.value.result_message == "Terminal too small (need 65x10)"
                )
