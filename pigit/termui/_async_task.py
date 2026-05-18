"""
Module: pigit/termui/_async_task.py
Description: Cancellable async task runner for non-blocking data loading.
    Results are delivered back to the main thread via a global queue
    polled by AppEventLoop each frame.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

import concurrent.futures
import logging
import queue
import threading
from typing import Any, Generic, TypeVar
from collections.abc import Callable

T = TypeVar("T")

_logger = logging.getLogger(__name__)

# Thread pool shared across all AsyncTask instances.  max_workers=3 keeps
# concurrency bounded while allowing the three main panels to load in parallel.
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

# Global queue for delivering async results back to the main thread.
_GLOBAL_QUEUE: queue.Queue[tuple[Callable[[Any], None], Any]] = queue.Queue()


class AsyncTask(Generic[T]):
    """Cancellable background task that delivers results to the main thread.

    Usage::

        task = AsyncTask()
        task.start(self._load_data, self._on_loaded)

    The worker thread executes *work*; when it finishes, the result is placed
    on a global queue.  :class:`~pigit.termui.event_loop.AppEventLoop` polls
    the queue once per frame and invokes the callback on the main thread.

    Calling :meth:`cancel` marks the task as cancelled.  If the worker
    finishes after cancellation, its result is silently dropped.  If the
    callback has already been queued, it is still invoked; the callback
    itself should check ``component.is_activated()`` to decide whether to
    apply the result.
    """

    def __init__(self) -> None:
        self._gen: int = 0
        self._lock = threading.Lock()

    def start(
        self,
        work: Callable[[], T],
        callback: Callable[[T], None],
    ) -> None:
        """Start a new background task, cancelling any previous one."""
        with self._lock:
            self._gen += 1
            current_gen = self._gen

        def _run() -> None:
            try:
                result = work()
            except Exception:
                _logger.debug("AsyncTask work failed", exc_info=True)
                return
            with self._lock:
                if current_gen != self._gen:
                    return
            _GLOBAL_QUEUE.put((callback, result))

        _executor.submit(_run)

    def cancel(self) -> None:
        """Mark the current task as cancelled.

        The worker thread will drop its result when it finishes.
        """
        with self._lock:
            self._gen += 1

    @classmethod
    def poll_all(cls) -> None:
        """Drain the global result queue and invoke callbacks.

        Must be called from the main thread (typically by AppEventLoop).
        """
        while True:
            try:
                callback, result = _GLOBAL_QUEUE.get_nowait()
            except queue.Empty:
                break
            try:
                callback(result)
            except Exception:
                _logger.exception("AsyncTask callback failed")
