# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_application.py
Description: Tests for pigit.termui.application.
Author: Zev
Date: 2026-04-17
"""

import pytest
from unittest.mock import MagicMock, patch, Mock

from pigit.termui._application import Application
from pigit.termui._component_base import Component


class DummyRoot(Component):
    NAME = "dummy"

    def _render_surface(self, surface):
        pass

    def fresh(self):
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
