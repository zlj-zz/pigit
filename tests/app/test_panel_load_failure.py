# -*- coding: utf-8 -*-
"""
Module: tests/app/test_panel_load_failure.py
Description: A failed panel load outlives the toast that announced it.
Author: Zev
Date: 2026-10-08
"""

from __future__ import annotations

import threading
import time
from unittest.mock import Mock, patch

from pigit.app_branch import BranchPanel
from pigit.app_status import StatusPanel
from pigit.app_theme import LOAD_FAILED_MARK
from pigit.git.model import Branch
from pigit.termui.async_task import AsyncTask
from pigit.termui.reactive import Signal
from pigit.termui.surface import Surface
from pigit.viewmodels.base import ViewModelBase

# What a load is waited on: the ViewModel's own state, never the panel state
# the test is about to assert.
_FAILED = lambda vm: vm.load_error.value is not None  # noqa: E731
_LOADED = lambda vm: bool(vm.items.value)             # noqa: E731


def _drained(predicate, timeout: float = 3.0) -> None:
    """Poll the result queue until *predicate* holds or time runs out."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        AsyncTask.poll_all()
        if predicate():
            return
        time.sleep(0.01)


class _BranchVm(ViewModelBase[Branch]):
    """A real ViewModel whose load can be made to fail on demand.

    The panels are driven through this rather than by poking signals, so the
    order real loads arrive in (``items`` first, then ``load_error``) is the
    order under test.
    """

    load_label = "Branches"

    def __init__(self, branches: list[Branch] | None = None) -> None:
        super().__init__()
        self.branches = branches or []
        self.error: Exception | None = None

    def _do_load(self) -> list[Branch]:
        if self.error is not None:
            raise self.error
        return self.branches


def _branch_panel(vm: _BranchVm) -> BranchPanel:
    return BranchPanel(vm=vm, get_git=lambda: Mock())


def _painted(panel) -> str:
    surface = Surface(80, 12)
    panel.resize((80, 12))
    panel.paint(surface)
    return "\n".join(surface.lines())


def _mount_failing() -> BranchPanel:
    vm = _BranchVm()
    vm.error = RuntimeError("index locked")
    panel = _branch_panel(vm)
    panel.mount()
    _drained(lambda: _FAILED(vm))
    return panel


class TestAFirstLoadThatFails:
    """Nothing older to keep, so the panel must say what happened. It used to
    keep showing the loading skeleton -- for good."""

    def test_the_skeleton_is_replaced_by_an_explanation(self):
        panel = _mount_failing()
        assert panel.loading is False
        assert "index locked" in _painted(panel)

    def test_the_panel_does_not_blame_the_scope(self):
        """An empty list on a *failed* load is not "no branches found"."""
        assert "No local branches found" not in _painted(_mount_failing())


class TestARefreshThatFails:
    def test_the_rows_stay_and_the_header_says_so(self):
        vm = _BranchVm([Branch("main", "0", "0", False)])
        panel = _branch_panel(vm)
        panel.mount()
        _drained(lambda: _LOADED(vm))
        assert [b.name for b in panel.branches] == ["main"]
        assert LOAD_FAILED_MARK not in _painted(panel)

        vm.error = RuntimeError("index locked")
        vm.refresh()
        _drained(lambda: _FAILED(vm))

        assert [b.name for b in panel.branches] == ["main"], "rows are kept"
        assert LOAD_FAILED_MARK in _painted(panel)


class TestASuccessClearsIt:
    def test_the_mark_goes_away(self):
        panel = _mount_failing()
        assert LOAD_FAILED_MARK in _painted(panel)

        panel._vm.error = None
        panel._vm.branches = [Branch("main", "0", "0", False)]
        panel._vm.refresh()
        _drained(lambda: _LOADED(panel._vm))

        assert LOAD_FAILED_MARK not in _painted(panel)
        assert "main" in _painted(panel)
        assert panel.empty_state is None, "Branch has no empty state of its own"

    def test_a_recovery_never_announces_an_empty_list(self):
        """Both signals wake the panel, so a recovery is handled twice. The
        order they are set in decides what the first pass believes: with the
        error still set it repaints the failure, which was true a moment ago.
        Set the other way round it would read the new rows with the error
        already cleared -- and say the list was empty."""
        vm = _BranchVm()
        vm.error = RuntimeError("index locked")
        panel = _branch_panel(vm)
        panel.mount()
        _drained(lambda: _FAILED(vm))

        seen: list[list[str]] = []
        original = panel.set_content
        panel.set_content = lambda content, _o=original: (
            seen.append(list(content)),
            _o(content),
        )[1]

        vm.error = None
        vm.branches = [Branch("main", "0", "0", False)]
        vm.refresh()
        _drained(lambda: _LOADED(vm))

        assert ["No local branches found."] not in seen
        assert seen[-1] == ["main"]

    def test_a_remount_does_not_wear_the_previous_failure(self):
        """The mark belongs to the load that produced it. A fresh one is in
        flight from the moment the panel is back on screen."""
        vm = _BranchVm()
        vm.error = RuntimeError("index locked")
        panel = _branch_panel(vm)
        panel.mount()
        _drained(lambda: _FAILED(vm))
        assert LOAD_FAILED_MARK in _painted(panel)

        panel.unmount()
        panel.mount()

        assert panel.loading is True, "the fresh load is still running"
        assert LOAD_FAILED_MARK not in _painted(panel)

    def test_the_panels_own_empty_state_comes_back(self):
        """Not just "the mark is gone": the panel shows the empty state it was
        built with, not the leftover failure text."""
        vm = Mock()
        vm.items = Signal([])
        vm.load_error = Signal(None)
        vm.repo_path = "/tmp/repo"
        panel = StatusPanel(vm=vm, default_view="flat")
        panel.mount()
        own = panel._empty_state_default
        assert own is not None, "Status has an empty state of its own"

        vm.load_error.set(RuntimeError("index locked"), force=True)
        assert panel.empty_state is not own

        vm.load_error.set(None, force=True)

        assert panel.empty_state is own
        assert "Working tree clean" in _painted(panel)


class TestTheToastIsStillSent:
    """The mark says "this is still true"; the toast says "this just
    happened". Dropping the toast would make a failure invisible to someone
    looking at another tab."""

    def test_a_failed_load_still_toasts(self):
        vm = _BranchVm()
        vm.error = RuntimeError("index locked")
        with patch("pigit.termui.overlay.show_toast") as toast:
            vm.refresh()
            _drained(lambda: toast.called)
        assert "Branches" in toast.call_args[0][0]


class TestTheViewModelsOwnState:
    def test_a_successful_load_clears_the_error(self):
        vm = _BranchVm([Branch("main", "0", "0", False)])
        vm.error = RuntimeError("index locked")
        vm.refresh()
        _drained(lambda: _FAILED(vm))
        assert isinstance(vm.load_error.value, RuntimeError)

        vm.error = None
        vm.refresh()
        _drained(lambda: vm.load_error.value is None and bool(vm.items.value))

        assert [b.name for b in vm.items.value] == ["main"]

    def test_a_failure_from_a_replaced_repo_does_not_mark_the_new_one(self):
        """A load still in flight when the repo changes belongs to the repo
        that started it."""
        vm = _BranchVm()
        vm.bind_repo_token("old")
        late = vm._guarded(vm._on_load_failed)

        vm.bind_repo_token("new")
        late(RuntimeError("index locked"))

        assert vm.load_error.value is None

    def test_a_failure_leaves_the_items_alone(self):
        """The old rows are the only thing the panel has; the error rides
        beside them rather than replacing them."""
        vm = _BranchVm([Branch("main", "0", "0", False)])
        vm.refresh()
        _drained(lambda: _LOADED(vm))

        vm.error = RuntimeError("index locked")
        vm.refresh()
        _drained(lambda: _FAILED(vm))

        assert [b.name for b in vm.items.value] == ["main"]


class TestTheFrameworkCallback:
    def _boom(self):
        return lambda: (_ for _ in ()).throw(RuntimeError("boom"))

    def test_a_task_without_a_failure_handler_is_unchanged(self):
        """The parameter is additive: every existing call site keeps its
        behaviour, including a failure one that only toasts."""
        task = AsyncTask()
        with patch("pigit.termui.overlay.show_toast") as toast:
            task.start(self._boom(), Mock())
            _drained(lambda: toast.called)
        assert toast.called

    def test_the_caller_hears_the_exception(self):
        task = AsyncTask()
        heard: list[BaseException] = []
        with patch("pigit.termui.overlay.show_toast"):
            task.start(self._boom(), Mock(), on_failure=heard.append)
            _drained(lambda: heard)
        assert len(heard) == 1
        assert isinstance(heard[0], RuntimeError)

    def test_a_superseded_failure_is_dropped(self):
        """``cancel()`` bumps the generation, so a worker that finishes
        afterwards reports nothing at all.

        The worker is held at a gate until the cancel has happened, so the
        outcome does not depend on which thread wins the race -- asserting it
        by cancelling immediately after ``start()`` passes or fails by
        scheduler luck.
        """
        task = AsyncTask()
        heard: list[BaseException] = []
        started, release = threading.Event(), threading.Event()

        def work():
            started.set()
            release.wait(2.0)
            raise RuntimeError("boom")

        with patch("pigit.termui.overlay.show_toast") as toast:
            task.start(work, Mock(), on_failure=heard.append)
            assert started.wait(2.0), "worker never started"
            task.cancel()
            release.set()
            _drained(lambda: False, timeout=0.3)  # give it time to finish
            assert heard == [] and not toast.called

    def test_a_failure_already_queued_is_still_delivered(self):
        """The other direction: ``cancel()`` only drops what has not been
        queued yet (see the class docstring on ``AsyncTask``)."""
        task = AsyncTask()
        heard: list[BaseException] = []
        with patch("pigit.termui.overlay.show_toast"):
            task.start(self._boom(), Mock(), on_failure=heard.append)
            _drained(lambda: heard)
            task.cancel()
        assert len(heard) == 1
