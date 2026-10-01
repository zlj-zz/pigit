# -*- coding: utf-8 -*-
"""
Module: tests/app/test_app_quit.py
Description: Quit asks before abandoning background work, and never strands.
Author: Zev
Date: 2026-09-30
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pigit.app import PigitApplication
from pigit.config_data import AppConfig
from pigit.termui import FeedbackKind
from pigit.termui.event_loop import ExitEventLoop


def _app() -> PigitApplication:
    return PigitApplication(config=AppConfig(repo_observe=False))


def _capturing_alert(app: PigitApplication) -> dict:
    """Show the dialog for real, but hand the answer back to the test."""
    captured: dict = {}

    def _alert(text, on_result, kind=None):
        captured.update(text=text, on_result=on_result, kind=kind)
        return True

    app._alert_dialog.alert = _alert
    return captured


def test_quit_with_nothing_running_leaves_immediately():
    app = _app()
    with patch("pigit.app.pending_count", return_value=0):
        with pytest.raises(ExitEventLoop) as exc:
            app.quit()
    assert exc.value.force is False


def test_quit_asks_before_abandoning_running_work():
    """Quitting is not instant: the interpreter joins every worker thread, so
    the wait has to be a choice the user can see."""
    app = _app()
    with patch("pigit.app.pending_count", return_value=2):
        captured = _capturing_alert(app)
        app.quit()  # returns: the question is on screen

    assert "2 background operation(s) still running" in captured["text"]
    assert "Quit anyway?" in captured["text"]
    assert captured["kind"] is FeedbackKind.WARNING


def test_answering_no_keeps_the_session_alive():
    app = _app()
    shutdowns: list[int] = []
    with (
        patch("pigit.app.pending_count", return_value=1),
        patch("pigit.app.shutdown_pending_tasks", lambda: shutdowns.append(1)),
    ):
        captured = _capturing_alert(app)
        app.quit()
        captured["on_result"](False)

    assert shutdowns == []


def test_answering_yes_forces_the_exit():
    app = _app()
    shutdowns: list[int] = []
    with (
        patch("pigit.app.pending_count", return_value=1),
        patch("pigit.app.shutdown_pending_tasks", lambda: shutdowns.append(1)),
    ):
        captured = _capturing_alert(app)
        app.quit()
        with pytest.raises(ExitEventLoop) as exc:
            captured["on_result"](True)

    assert shutdowns == [1]
    assert exc.value.force is True


def test_a_blocked_dialog_does_not_strand_the_user():
    """``alert`` returns False while another modal owns the screen. Refusing
    to quit there would leave the key doing nothing, with no way out."""
    app = _app()
    app._alert_dialog.alert = lambda *a, **k: False

    with patch("pigit.app.pending_count", return_value=3):
        with pytest.raises(ExitEventLoop) as exc:
            app.quit()

    assert exc.value.force is False
