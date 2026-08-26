# -*- coding: utf-8 -*-
"""
Module: tests/observe/test_coordinator.py
Description: Tests for RefreshCoordinator, RepoObserver, and overlay defer.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import queue
from typing import Any

from pigit.observe.backend import FakeBackend
from pigit.observe.clock import FakeClock
from pigit.observe.coordinator import RefreshCoordinator
from pigit.observe.observer import RepoObserver
from pigit.observe.overlay import should_defer_repo_refresh
from pigit.observe.types import ChangeKind, ObserveContext, PathSignal
from pigit.termui.types import LayerKind


def _ctx(repo: str = "/repo") -> ObserveContext:
    git = f"{repo}/.git"
    return ObserveContext(repo_root=repo, git_dir=git, common_dir=git)


def test_fake_clock_starts_and_advances():
    clock = FakeClock(start=1.0)
    assert clock.monotonic() == 1.0
    clock.advance(0.3)
    assert clock.monotonic() == 1.3


def test_debounce_merges_bursts():
    batches: list[Any] = []
    clock = FakeClock()
    q: queue.Queue[PathSignal] = queue.Queue()
    coord = RefreshCoordinator(
        q,
        clock=clock,
        debounce_s=0.3,
        defer_fn=lambda: False,
        on_batch=batches.append,
        ctx_provider=_ctx,
    )
    q.put(PathSignal(path="/repo/.git/HEAD", mtime_ns=1))
    coord.drain()
    assert batches == []

    clock.advance(0.3)
    q.put(PathSignal(path="/repo/.git/index", mtime_ns=2))
    coord.drain()
    clock.advance(0.3)
    coord.drain()

    assert len(batches) == 1
    assert ChangeKind.HEAD in batches[0].kinds
    assert ChangeKind.INDEX in batches[0].kinds


def test_defer_while_modal_then_flush():
    batches: list[Any] = []
    deferred = True
    clock = FakeClock()
    q: queue.Queue[PathSignal] = queue.Queue()
    coord = RefreshCoordinator(
        q,
        clock=clock,
        debounce_s=0.3,
        defer_fn=lambda: deferred,
        on_batch=batches.append,
        ctx_provider=_ctx,
    )
    q.put(PathSignal(path="/repo/.git/HEAD", mtime_ns=1))
    coord.drain()
    clock.advance(0.3)
    coord.drain()
    assert batches == []

    deferred = False
    coord.drain()
    assert len(batches) == 1
    assert ChangeKind.HEAD in batches[0].kinds


def test_quiet_window_flushes_without_new_signals():
    batches: list[Any] = []
    clock = FakeClock()
    q: queue.Queue[PathSignal] = queue.Queue()
    coord = RefreshCoordinator(
        q,
        clock=clock,
        debounce_s=0.3,
        defer_fn=lambda: False,
        on_batch=batches.append,
        ctx_provider=_ctx,
    )
    q.put(PathSignal(path="/repo/.git/HEAD", mtime_ns=1))
    coord.drain()
    assert batches == []
    clock.advance(0.3)
    coord.drain()
    assert len(batches) == 1


class _FakeLayer:
    def __init__(self) -> None:
        self._tops: dict[LayerKind, object | None] = {
            LayerKind.MODAL: None,
            LayerKind.SHEET: None,
            LayerKind.TOAST: None,
        }

    def top(self, kind: LayerKind) -> object | None:
        return self._tops.get(kind)

    def set_top(self, kind: LayerKind, value: object | None) -> None:
        self._tops[kind] = value


class _FakeRoot:
    def __init__(self) -> None:
        self._layer_stack = _FakeLayer()


def test_should_defer_modal_or_sheet_not_toast():
    root = _FakeRoot()
    assert should_defer_repo_refresh(root) is False

    root._layer_stack.set_top(LayerKind.TOAST, object())
    assert should_defer_repo_refresh(root) is False

    root._layer_stack.set_top(LayerKind.TOAST, None)
    root._layer_stack.set_top(LayerKind.MODAL, object())
    assert should_defer_repo_refresh(root) is True

    root._layer_stack.set_top(LayerKind.MODAL, None)
    root._layer_stack.set_top(LayerKind.SHEET, object())
    assert should_defer_repo_refresh(root) is True


def test_observer_poll_into_queue():
    signals = [
        [PathSignal(path="/repo/.git/HEAD", mtime_ns=1)],
        [PathSignal(path="/repo/.git/index", mtime_ns=2)],
    ]
    backend = FakeBackend(scripted=signals)
    backend.start([])
    q: queue.Queue[PathSignal] = queue.Queue()
    observer = RepoObserver(backend=backend, out_queue=q)
    observer.poll_into_queue()
    assert q.get_nowait().path.endswith("HEAD")
    observer.poll_into_queue()
    assert q.get_nowait().path.endswith("index")
    observer.poll_into_queue()
    assert q.empty()
