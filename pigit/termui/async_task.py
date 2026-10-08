"""
Module: pigit/termui/async_task.py
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

_DEFAULT_LABEL = "Background task"

# Workers currently executing. Counted inside the worker rather than around
# ``_executor.submit`` so a task cancelled before it ever starts (see
# :func:`shutdown_pending_tasks`) is not counted — this number is what the
# quit confirmation shows the user, and it claims the tasks are *running*.
_in_flight = 0
_in_flight_lock = threading.Lock()


def _counted(work: Callable[[], None]) -> Callable[[], None]:
    """Wrap a worker so it is counted for as long as it actually runs.

    The decrement lives in ``finally`` because every other exit — a raised
    exception, the failure path, cancellation — must still release the count.
    A leaked count would make :func:`pending_count` permanent, and the quit
    confirmation would then never let the user past it.
    """

    def _run() -> None:
        global _in_flight
        with _in_flight_lock:
            _in_flight += 1
        try:
            work()
        finally:
            with _in_flight_lock:
                _in_flight -= 1

    return _run


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
    itself should check ``component.is_mounted()`` to decide whether to
    apply the result.
    """

    def __init__(self) -> None:
        self._gen: int = 0
        self._lock = threading.Lock()

    def start(
        self,
        work: Callable[[], T],
        callback: Callable[[T], None],
        *,
        label: str = _DEFAULT_LABEL,
        on_failure: Callable[[BaseException], None] | None = None,
    ) -> None:
        """Start a new background task, cancelling any previous one.

        Args:
            work: Blocking callable executed on the worker thread.
            callback: Invoked on the main thread with the result.
            label: Human name for the task, used when reporting a failure.
                Resolve it here — at the call site — rather than deriving it
                from ``callback``: callers overwhelmingly pass a
                ``ViewModelBase._guarded`` wrapper, whose ``__name__`` is
                ``deliver`` for every task in the app.
            on_failure: Invoked on the main thread with the exception when
                ``work`` raises. Without it the failure only reaches the
                global toast, which is gone in three seconds — a caller that
                owns state (a panel that must stop saying "loading") passes
                this to hear about it too.
        """
        with self._lock:
            self._gen += 1
            current_gen = self._gen

        def _run() -> None:
            try:
                result = work()
            except Exception as exc:
                _logger.exception("AsyncTask work failed: %s", label)
                self._put_failure(current_gen, label, exc, on_failure)
                return
            with self._lock:
                if current_gen != self._gen:
                    return
                _GLOBAL_QUEUE.put((callback, result))

        _executor.submit(_counted(_run))

    def start_stream(
        self,
        work: Callable[[Callable[[T], bool]], None],
        callback: Callable[[T], None],
        *,
        label: str = _DEFAULT_LABEL,
    ) -> None:
        """Start a streaming task whose result arrives in batches.

        ``work`` receives an ``emit`` callable and may call it any number of
        times from the worker thread; each batch reaches ``callback`` on the
        main thread, exactly like :meth:`start`. ``emit`` returns ``False``
        once the task has been superseded (``cancel`` or a newer
        ``start``/``start_stream``), and the worker is expected to stop
        producing — which is what actually cancels a long read such as a
        ``git log`` generator: dropping it closes the pipe.

        Batches already queued when the stream is superseded are still
        delivered, so the callback must also validate what it applies.
        """
        with self._lock:
            self._gen += 1
            current_gen = self._gen

        def emit(batch: T) -> bool:
            with self._lock:
                if current_gen != self._gen:
                    return False
            _GLOBAL_QUEUE.put((callback, batch))
            return True

        def _run() -> None:
            try:
                work(emit)
            except Exception as exc:
                _logger.exception("AsyncTask stream failed: %s", label)
                self._put_failure(current_gen, label, exc)

        _executor.submit(_counted(_run))

    def _put_failure(
        self,
        current_gen: int,
        label: str,
        exc: BaseException,
        on_failure: Callable[[BaseException], None] | None = None,
    ) -> None:
        """Hand a worker failure to the main thread, unless superseded.

        Rides the same ``(callback, result)`` queue as successful results, so
        ``poll_all`` needs no type branch. The import is lazy because the
        overlay layer sits above this one.
        """
        from .overlay import report_async_failure

        with self._lock:
            if current_gen != self._gen:
                return
            # Both destinations are fed: the caller's handler updates whatever
            # state it owns, and the toast is how the failure reaches a user
            # who is not looking at that state.
            if on_failure is not None:
                _GLOBAL_QUEUE.put((on_failure, exc))
            _GLOBAL_QUEUE.put((report_async_failure, (label, exc)))

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
        count = 0
        while True:
            try:
                callback, result = _GLOBAL_QUEUE.get_nowait()
            except queue.Empty:
                break
            count += 1
            _logger.debug(
                "[ASYNC] poll_all: invoking callback=%s",
                getattr(callback, "__name__", callback),
            )
            try:
                callback(result)
            except Exception:
                _logger.exception("AsyncTask callback failed")
        if count:
            _logger.debug("[ASYNC] poll_all: processed %d callbacks", count)
            from ._runtime_context import request_render

            request_render()


def pending_count() -> int:
    """Number of background workers currently executing."""
    with _in_flight_lock:
        return _in_flight


def shutdown_pending_tasks() -> None:
    """Discard queued work and stop accepting more.

    Called on the way out so quitting does not have to wait for a backlog the
    user never asked to finish; it shortens the tail to the longest single
    task already running. Those running tasks cannot be cancelled — a thread
    has no cancellation point — so ``wait=False`` here still leaves the
    interpreter's own shutdown joining them.
    """
    _executor.shutdown(wait=False, cancel_futures=True)


def run_async(
    work: Callable[[], T],
    callback: Callable[[T], Any],
    *,
    label: str = _DEFAULT_LABEL,
) -> AsyncTask[T]:
    """Run blocking work in a background thread; deliver result to main thread.

    Args:
        work: Blocking function executed in ThreadPoolExecutor.
        callback: Invoked on the main thread with the result.
        label: Human name for the task, used when reporting a failure.

    Returns:
        AsyncTask handle; caller can ``.cancel()`` to drop the result.
    """
    task = AsyncTask[T]()
    task.start(work, callback, label=label)
    return task
