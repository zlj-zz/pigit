# -*- coding: utf-8 -*-
"""
Module: pigit/observe/observer.py
Description: RepoObserver polls a backend and enqueues PathSignals.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import queue
from typing import Callable

from .backend import ObservationBackend
from .types import ObserveContext, PathSignal, WatchRoot

DEFAULT_QUEUE_MAXSIZE = 256


class RepoObserver:
    """Pulls signals from an ObservationBackend onto a queue.Queue.

    The UI (or a helper) must call ``poll_into_queue``; this class does not
    spawn threads. Push backends may still enqueue elsewhere and return []
    from ``poll``.
    """

    def __init__(
        self,
        backend: ObservationBackend,
        out_queue: queue.Queue[PathSignal] | None = None,
        ctx_provider: Callable[[], ObserveContext] | None = None,
        *,
        maxsize: int = DEFAULT_QUEUE_MAXSIZE,
    ) -> None:
        self._backend = backend
        self._queue = (
            out_queue if out_queue is not None else queue.Queue(maxsize=maxsize)
        )
        self._ctx_provider = ctx_provider

    @property
    def queue(self) -> queue.Queue[PathSignal]:
        """Queue that receives PathSignals."""
        return self._queue

    def start(self, roots: list[WatchRoot]) -> None:
        """Start the underlying backend with ``roots``."""
        self._backend.start(roots)

    def update_roots(self, roots: list[WatchRoot]) -> None:
        """Update backend roots without a full stop (keeps mtime baselines)."""
        update = getattr(self._backend, "update_roots", None)
        if callable(update):
            update(roots)
        else:
            self._backend.start(roots)

    def stop(self) -> None:
        """Stop the underlying backend."""
        self._backend.stop()

    def poll_into_queue(self) -> int:
        """Poll the backend and enqueue signals.

        When the queue is full, drop the oldest raw signal then retry put
        (bounded coalesce). Returns the number of signals enqueued.
        """
        signals = self._backend.poll()
        enqueued = 0
        for signal in signals:
            if self._put_coalesce(signal):
                enqueued += 1
        return enqueued

    def _put_coalesce(self, signal: PathSignal) -> bool:
        """Put ``signal``; on Full drop oldest once and retry."""
        try:
            self._queue.put_nowait(signal)
            return True
        except queue.Full:
            pass
        try:
            self._queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self._queue.put_nowait(signal)
            return True
        except queue.Full:
            return False
