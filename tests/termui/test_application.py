# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_application.py
Description: Tests for pigit.termui.application.
Author: Zev
Date: 2026-04-17
"""

from unittest.mock import MagicMock, patch

from pigit.termui._application import Application
from pigit.termui._component import Component


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
        with patch("pigit.termui._application.AppEventLoop") as MockLoop:
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
        with patch("pigit.termui._application.AppEventLoop") as MockLoop:
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
        with patch("pigit.termui._application.AppEventLoop") as MockLoop:
            MockLoop.return_value = MagicMock()
            app.run()
            MockLoop.call_args.kwargs["on_after_start"]()
            assert app.hooked is True

    def test_destroy_called_after_loop_exit(self):
        """root.destroy() must be called in finally block after loop exits."""
        app = DummyApp()
        with patch("pigit.termui._application.AppEventLoop") as MockLoop:
            MockLoop.return_value = MagicMock()
            app.run()
            assert app._root is None
