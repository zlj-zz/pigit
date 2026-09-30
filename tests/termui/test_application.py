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
from pigit.termui.root import ComponentRoot


class DummyRoot(Component):
    NAME = "dummy"

    def paint(self, surface):
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

    def test_on_exit_called_before_destroy(self):
        """on_exit runs in finally before root.destroy()."""
        order: list[str] = []

        class Hooked(DummyApp):
            def on_exit(self):
                order.append("on_exit")
                assert self._root is not None

        app = Hooked()
        with patch("pigit.termui.application.AppEventLoop") as MockLoop:
            MockLoop.return_value = MagicMock()
            with patch.object(
                ComponentRoot,
                "destroy",
                autospec=True,
                side_effect=lambda self: order.append("destroy"),
            ):
                app.run()
        assert order == ["on_exit", "destroy"]
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


class TestForcedExit:
    """A forced quit must not wait for worker threads.

    Interpreter shutdown joins every non-daemon thread, so a network call
    against an unreachable remote would keep the process alive indefinitely
    after the user already said to quit.
    """

    def _run_raising(self, app, exc: ExitEventLoop):
        with patch("pigit.termui.application.AppEventLoop") as MockLoop:
            MockLoop.return_value = MagicMock()
            MockLoop.return_value.run.side_effect = exc
            app.run()

    def test_forced_quit_exits_without_joining(self, monkeypatch):
        exits: list[int] = []
        monkeypatch.setattr(
            "pigit.termui.application._exit_without_joining", exits.append
        )
        app = DummyApp()

        self._run_raising(app, ExitEventLoop("Quit", exit_code=3, force=True))

        assert exits == [3]

    def test_an_ordinary_quit_winds_down_normally(self, monkeypatch):
        exits: list[int] = []
        monkeypatch.setattr(
            "pigit.termui.application._exit_without_joining", exits.append
        )
        app = DummyApp()

        self._run_raising(app, ExitEventLoop("Quit", exit_code=0))

        assert exits == []

    def test_cleanup_runs_before_the_forced_exit(self, monkeypatch):
        """``os._exit`` performs no cleanup of its own, so everything that
        restores the terminal must already have happened."""
        observed: dict = {}
        app = DummyApp()

        def _capture(code: int) -> None:
            observed["root"] = app._root
            observed["code"] = code

        monkeypatch.setattr("pigit.termui.application._exit_without_joining", _capture)

        self._run_raising(app, ExitEventLoop("Quit", exit_code=0, force=True))

        assert observed == {"root": None, "code": 0}

    def test_forced_quit_still_propagates_to_the_caller(self, monkeypatch):
        """``_run_body`` records the flag but must not swallow the exception
        that ``run_with_result`` turns into an ``(exit_code, message)``."""
        monkeypatch.setattr(
            "pigit.termui.application._exit_without_joining", lambda _code: None
        )
        app = DummyApp()

        with patch("pigit.termui.application.AppEventLoop") as MockLoop:
            MockLoop.return_value = MagicMock()
            MockLoop.return_value.run.side_effect = ExitEventLoop(
                "done", exit_code=7, result_message="picked"
            )
            assert app.run_with_result() == (7, "picked")

    def test_exit_helper_flushes_logging_before_exiting(self, monkeypatch):
        """``os._exit`` skips atexit, so buffered log records would be lost."""
        from pigit.termui import application

        order: list[str] = []
        monkeypatch.setattr(application.logging, "shutdown", lambda: order.append("flush"))
        monkeypatch.setattr(application.os, "_exit", lambda code: order.append(f"exit:{code}"))

        application._exit_without_joining(2)

        assert order == ["flush", "exit:2"]

    def test_a_failing_on_exit_hook_cannot_skip_the_forced_exit(self, monkeypatch):
        """``on_exit`` is a user-supplied hook. If it raises during the unwind
        of a forced quit, the exit must still happen — otherwise the process
        falls back to joining workers, which is the hang this exists for."""
        exits: list[int] = []
        monkeypatch.setattr(
            "pigit.termui.application._exit_without_joining", exits.append
        )

        class _BadExitHook(DummyApp):
            def on_exit(self) -> None:
                raise RuntimeError("hook blew up")

        app = _BadExitHook()

        with pytest.raises(RuntimeError):
            self._run_raising(app, ExitEventLoop("Quit", exit_code=5, force=True))

        assert exits == [5]
