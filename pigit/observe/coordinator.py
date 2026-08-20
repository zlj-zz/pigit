# -*- coding: utf-8 -*-
"""
Module: pigit/observe/coordinator.py
Description: UI-thread drain, classify, debounce, and defer for ChangeBatches.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import queue
from collections.abc import Callable

from .classify import classify_path_signal
from .clock import MonotonicClock, SystemClock
from .types import ChangeBatch, ChangeKind, ObserveContext, PathSignal

DEFAULT_DEBOUNCE_S = 0.3


class RefreshCoordinator:
    """Drain PathSignals on the UI thread into debounced ChangeBatches.

    Must not import application code; sinks are injected via ``on_batch``.
    """

    def __init__(
        self,
        signal_queue: queue.Queue[PathSignal],
        *,
        clock: MonotonicClock | None = None,
        debounce_s: float = DEFAULT_DEBOUNCE_S,
        defer_fn: Callable[[], bool] | None = None,
        on_batch: Callable[[ChangeBatch], None] | None = None,
        ctx_provider: Callable[[], ObserveContext],
    ) -> None:
        self._queue = signal_queue
        self._clock = clock if clock is not None else SystemClock()
        self._debounce_s = debounce_s
        self._defer_fn = defer_fn if defer_fn is not None else (lambda: False)
        self._on_batch = on_batch if on_batch is not None else (lambda _batch: None)
        self._ctx_provider = ctx_provider
        self._pending_kinds: set[ChangeKind] = set()
        self._pending_paths: set[str] = set()
        self._last_merge_at: float | None = None

    def drain(self) -> None:
        """Pull queued signals, merge, and flush when quiet and not deferred."""
        self._ingest_queue()
        self._try_flush()

    def _ingest_queue(self) -> None:
        """Classify and merge all currently queued PathSignals."""
        got_new = False
        while True:
            try:
                signal = self._queue.get_nowait()
            except queue.Empty:
                break
            ctx = self._ctx_provider()
            kinds, paths = classify_path_signal(signal, ctx)
            if kinds or paths:
                self._pending_kinds |= set(kinds)
                self._pending_paths |= set(paths)
                got_new = True
        if got_new:
            self._last_merge_at = self._clock.monotonic()

    def _try_flush(self) -> None:
        """Emit a ChangeBatch when debounce elapsed and refresh is not deferred."""
        if not self._pending_kinds and not self._pending_paths:
            return
        if self._last_merge_at is None:
            return
        if self._clock.monotonic() - self._last_merge_at < self._debounce_s:
            return
        if self._defer_fn():
            return
        batch = ChangeBatch(
            kinds=frozenset(self._pending_kinds),
            paths=frozenset(self._pending_paths),
        )
        self._pending_kinds.clear()
        self._pending_paths.clear()
        self._last_merge_at = None
        self._on_batch(batch)
