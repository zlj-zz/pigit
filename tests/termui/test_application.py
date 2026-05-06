# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_application.py
Description: Tests for pigit.termui.application.
Author: Zev
Date: 2026-04-17
"""

import pytest
from unittest.mock import MagicMock, patch, Mock

from pigit.termui._application import Application, _ApplicationEventLoop
from pigit.termui._component_base import Component, _set_focus_chain
from pigit.termui._root import ComponentRoot
from pigit.termui.types import LayerKind


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
    def test_run_builds_root_and_starts_loop(self):
        app = DummyApp()
        with patch("pigit.termui._application._ApplicationEventLoop") as MockLoop:
            mock_loop = MagicMock()
            MockLoop.return_value = mock_loop
            app.run()
            mock_loop.run.assert_called_once()

    def test_after_start_hook_called(self):
        class Hooked(DummyApp):
            def after_start(self):
                self.hooked = True

        app = Hooked()
        with patch("pigit.termui._application._ApplicationEventLoop") as MockLoop:
            mock_loop = MagicMock()

            def _simulate_run():
                mock_loop.after_start()

            mock_loop.run = Mock(side_effect=_simulate_run)
            mock_loop.after_start = Mock(side_effect=app.after_start)
            MockLoop.return_value = mock_loop
            app.run()
            mock_loop.run.assert_called_once()
            assert app.hooked is True

    def test_destroy_called_after_loop_exit(self):
        """root.destroy() must be called in finally block after loop exits."""
        app = DummyApp()
        with patch("pigit.termui._application._ApplicationEventLoop") as MockLoop:
            mock_loop = MagicMock()
            MockLoop.return_value = mock_loop
            app.run()
            assert app._root is not None
            # destroy() was called during cleanup in finally block


class _FakeOverlay(Component):
    NAME = "overlay"

    def __init__(self):
        super().__init__()
        self.open = True

    def _render_surface(self, surface):
        pass

    def refresh(self):
        pass


class TestApplicationEventLoop:
    def test_app_binding_closes_overlay_restores_focus(self):
        """When an app-level binding closes an open overlay, focus must be
        restored to the body component tree so background panels undim."""
        body = DummyRoot()
        root = ComponentRoot(body)

        class _App(Application):
            BINDINGS = [("x", "close_overlay")]

            def build_root(self):
                return body

            def close_overlay(self):
                root._layer_stack.pop(LayerKind.MODAL)

        app = _App()
        loop = _ApplicationEventLoop(root, app, alt=False)
        loop.before_dispatch_key = Mock()
        loop.render = Mock()

        # Simulate an overlay being open
        overlay = _FakeOverlay()
        root._layer_stack.push(LayerKind.MODAL, overlay)
        _set_focus_chain(overlay)

        # Dispatch the app binding that closes the overlay
        loop._dispatch_semantic_string("x")

        # Focus should be restored to body leaf
        assert body.is_focus_leaf
        loop.render.assert_called_once()
