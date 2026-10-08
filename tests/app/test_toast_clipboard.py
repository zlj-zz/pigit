# -*- coding: utf-8 -*-
"""
Module: tests/app/test_toast_clipboard.py
Description: Error toasts are mirrored to the clipboard; other toasts are not.
Author: Zev
Date: 2026-10-08
"""

from __future__ import annotations

import pytest

from pigit.app import PigitApplication
from pigit.config_data import AppConfig
from pigit.termui import Component, FeedbackKind, Segment, show_toast
from pigit.termui.overlay import get_toast_signal, report_async_failure
from pigit.termui.root import ComponentRoot
from pigit.termui._runtime_context import (
    RuntimeContext,
    _runtime_ctx,
    reset_overlay_host,
    set_overlay_host,
)

ERROR = FeedbackKind.ERROR


class _Body(Component):
    """Stand-in for the app body: the overlay host needs something to paint."""

    def paint(self, surface) -> None:
        pass


class _Recorder:
    """``Signal.subscribe`` requires a *bound method*, so a closure will not do."""

    def __init__(self) -> None:
        self.seen: list = []

    def record(self, value) -> None:
        self.seen.append(value)


@pytest.fixture
def runtime():
    """A fresh runtime context *and* a clean toast channel.

    The toast signal is process-global and each subscriber lives as long as
    the object holding it. A ``PigitApplication`` sits in a reference cycle, so
    it is only reclaimed by a cyclic GC pass -- which pytest does not run -- and
    every app an earlier test built would still be subscribed, copying each
    toast once more. Clearing here makes the counts below exact: one toast,
    one copy, so a handler registered twice would still be caught.
    """
    ctx = RuntimeContext()
    token = _runtime_ctx.set(ctx)
    get_toast_signal().clear_subscribers()
    yield ctx
    get_toast_signal().clear_subscribers()
    _runtime_ctx.reset(token)
    reset_overlay_host()


def _mount_host(runtime: RuntimeContext) -> ComponentRoot:
    root = ComponentRoot(_Body())
    runtime.overlay_host = root
    runtime.focus_manager = root._focus_manager
    set_overlay_host(root)
    return root


@pytest.fixture
def app(runtime: RuntimeContext) -> PigitApplication:
    """A real app, so the subscription under test is the one the app installs."""
    application = PigitApplication(config=AppConfig(repo_observe=False))
    _mount_host(runtime)
    yield application
    application._toast_unsub()


def _watch() -> tuple[_Recorder, list]:
    recorder = _Recorder()
    get_toast_signal().subscribe(recorder.record)
    return recorder, recorder.seen


class TestWhatTheSignalCarries:
    """The signal is the framework's, so it reports every toast; deciding which
    kinds deserve a copy is the app's business."""

    def test_an_error_toast_reports_its_message_and_kind(self, runtime):
        _mount_host(runtime)
        _recorder, seen = _watch()
        show_toast("branch is locked", kind=ERROR)
        assert seen == [("branch is locked", ERROR)]

    def test_a_non_error_toast_is_reported_too(self, runtime):
        _mount_host(runtime)
        _recorder, seen = _watch()
        show_toast("Copied", kind=FeedbackKind.SUCCESS)
        assert seen == [("Copied", FeedbackKind.SUCCESS)]

    def test_a_segments_toast_reports_no_kind(self, runtime):
        """``segments`` suppresses ``kind``, and the signal carries the kind as
        it was actually rendered rather than the one that was passed."""
        _mount_host(runtime)
        _recorder, seen = _watch()
        show_toast("", segments=[Segment("x", fg=(1, 2, 3))], kind=ERROR)
        assert seen == [("", None)]

    def test_without_an_overlay_host_nothing_is_reported(self, runtime):
        """No host means no toast was shown, so there is nothing to mirror."""
        _recorder, seen = _watch()
        assert show_toast("nobody is listening", kind=ERROR) is None
        assert seen == []


class TestErrorToastsAreCopied:

    def test_an_error_toast_reaches_the_clipboard(self, app, clipboard):
        show_toast("fatal: not a git repository", kind=ERROR)
        assert clipboard == ["fatal: not a git repository"]

    def test_a_non_error_toast_is_left_alone(self, app, clipboard):
        show_toast("Copied a1b2c3d", kind=FeedbackKind.SUCCESS)
        show_toast("nothing special here")
        assert clipboard == []

    def test_an_empty_message_is_not_copied(self, app, clipboard):
        """Copying it would clear the clipboard, which is worse than leaving it
        stale. Reachable: the failure paths format ``str(exc)``, and a bare
        ``Exception()`` stringifies to ``""``."""
        assert str(Exception()) == ""
        show_toast(str(Exception()), kind=ERROR)
        assert clipboard == []

    def test_a_segments_toast_is_not_copied(self, app, clipboard):
        show_toast("", segments=[Segment("boom", fg=(1, 2, 3))], kind=ERROR)
        assert clipboard == []

    def test_a_background_failure_is_copied(self, app, clipboard):
        """The user never asked for this one: ``report_async_failure`` fires for
        any failed task, including the loads the file watcher triggers. Its text
        is what you would paste into an issue, so it is copied like the rest."""
        report_async_failure(("Working tree status", RuntimeError("index locked")))
        assert clipboard == ["Working tree status failed: index locked"]
