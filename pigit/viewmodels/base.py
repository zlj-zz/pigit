"""
Module: pigit/viewmodels/base.py
Description: ViewModel base class and shared abstractions.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar, cast, runtime_checkable
from collections.abc import Callable

from pigit.termui.async_task import AsyncTask
from pigit.termui.reactive import Signal

T = TypeVar("T")
_S = TypeVar("_S")


@dataclass
class ActionResult:
    """Result of a ViewModel action. Panel decides whether to refresh.

    ``refused`` marks the third outcome: the action never ran, because another
    one holds the worktree gate. It is not a failure -- nothing was attempted
    -- and it is reported on a different channel for that reason.
    """

    success: bool
    message: str = ""
    should_refresh: bool = False
    refused: bool = False


WORKTREE_BUSY_MESSAGE = "Another working-tree operation is still running"


class WorktreeGate:
    """Single-flight guard for operations that rewrite the working tree.

    One instance per session, shared by every ViewModel: a checkout started on
    the Branch panel and a stash pop on Status would otherwise rewrite the same
    working tree at once. The observe coordinator also reads :attr:`busy` — its
    ``defer_fn`` pauses repo refresh while a rewrite is in flight, because
    polling ``git status`` against a half-written tree flickers the Status
    panel and can publish a half-applied state as if it were final.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._busy = False

    @property
    def busy(self) -> bool:
        """True while a working-tree rewrite is running."""
        return self._busy

    def acquire(self) -> bool:
        """Claim the gate; False when another rewrite already holds it."""
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            return True

    def release(self) -> None:
        """Release the gate."""
        with self._lock:
            self._busy = False


def run_gated(gate: WorktreeGate, op: Callable[[], ActionResult]) -> ActionResult:
    """Run a working-tree rewrite under the session gate, or refuse it.

    Every path that writes the working tree goes through here, so a checkout
    still running on a worker can never overlap a discard or a conflict
    resolution started from the keyboard.
    """
    if not gate.acquire():
        return ActionResult(
            success=False, message=WORKTREE_BUSY_MESSAGE, refused=True
        )
    try:
        return op()
    finally:
        gate.release()


@runtime_checkable
class IListViewModel(Protocol, Generic[T]):
    """Protocol for list-based panel ViewModels."""

    @property
    def items(self) -> Signal[list[T]]:
        """Current list of items. Panel subscribes via bind_signals()."""
        ...

    @property
    def load_error(self) -> Signal[BaseException | None]:
        """Last load failure, or None.

        A panel subscribes to this alongside ``items``: a failure never
        reaches the success callback, so this is the only notice it gets.
        """
        ...

    def refresh(self) -> None:
        """Trigger async data refresh. VM updates ``items`` Signal when done."""
        ...

    def dispose(self) -> None:
        """Cancel pending async work and clean up subscriptions."""
        ...


class ViewModelBase(Generic[T]):
    """Base class for concrete ViewModels.

    Manages the AsyncTask loader and the ``items`` Signal.
    Subclasses override ``_do_load()`` to fetch data.
    """

    _NO_SNAPSHOT = object()

    #: Human name for this VM's background load, reported if the worker
    #: raises. Subclasses override it; the default is a fallback only.
    load_label: str = "Data"

    def __init__(self) -> None:
        self._loader = AsyncTask()
        self._items: Signal[list[T]] = Signal([])
        # Last load failure, or None. Cleared by the next successful load.
        self._load_error: Signal[BaseException | None] = Signal(None)
        self._unsubs: list[Callable[[], None]] = []
        self._inspector_key: object = self._NO_SNAPSHOT
        self._inspector_value: object | None = None
        # Snapshot builds may run on an AsyncTask worker thread while a
        # refresh invalidates the cache on the UI thread.
        self._inspector_lock = threading.Lock()
        # App bumps this on repo switch; in-flight loads capture the old value.
        self._repo_token: object | None = None

    @property
    def items(self) -> Signal[list[T]]:
        return self._items

    @property
    def load_error(self) -> Signal[BaseException | None]:
        return self._load_error

    def bind_repo_token(self, token: object | None) -> None:
        """Point this VM at the app's current repo generation token."""
        self._repo_token = token

    def refresh(self) -> None:
        self._loader.start(
            self._do_load,
            self._guarded(self._on_loaded),
            label=self.load_label,
            on_failure=self._guarded(self._on_load_failed),
        )

    def _guarded(self, callback: Callable[[_S], None]) -> Callable[[_S], None]:
        """Wrap a load callback so a superseded repo token drops the result."""
        token = self._repo_token

        def deliver(data: _S) -> None:
            if token is not self._repo_token:
                return
            callback(data)

        return deliver

    def _do_load(self) -> list[T]:
        """Override to perform the actual data fetch."""
        raise NotImplementedError

    def _on_loaded(self, data: list[T]) -> None:
        # force=True: a refresh that re-produces the same value (e.g. an empty
        # tree) must still notify so loading state clears and empty-state
        # renders; Signal.set alone would skip the unchanged value.
        self._items.set(data, force=True)
        # Cleared after the rows, not before. Each signal wakes the panel
        # separately, so a recovery is handled twice; this order makes the
        # first pass see the old error beside the new rows and paint the
        # failure state -- which is still true of the load that just ended --
        # and the second pass clear it. Clearing first would instead have the
        # first pass read the new rows with the error already gone, and
        # announce an empty list that is not empty.
        self._load_error.set(None)
        # A fresh load may have changed the underlying git state, so any
        # memoized inspector snapshot is stale.
        with self._inspector_lock:
            self._inspector_key = self._NO_SNAPSHOT
            self._inspector_value = None

    def _on_load_failed(self, exc: BaseException) -> None:
        """Record a failed load so the panel can stop claiming it is loading.

        The worker's exception never reaches ``_on_loaded``, so without this
        the panel keeps its old rows -- or, on a first load, its skeleton --
        and the only sign anything went wrong is a toast that expires.
        """
        self._load_error.set(exc)

    def _memo_inspector(self, key: object, build: Callable[[], _S | None]) -> _S | None:
        """Return a memoized inspector snapshot for *key*.

        Reopening the inspector on an unchanged selection reuses the previous
        snapshot instead of re-running git reads. Any refresh invalidates it
        via :meth:`_on_loaded`.

        ``build`` runs outside the lock (it spawns git subprocesses); the
        result is cached only if a refresh did not invalidate the slot while
        it was running.
        """
        with self._inspector_lock:
            if self._inspector_key == key:
                return cast(_S | None, self._inspector_value)
            previous = self._inspector_key
        value = build()
        with self._inspector_lock:
            if self._inspector_key == previous:
                self._inspector_key = key
                self._inspector_value = value
        return value

    def item_at(self, idx: int) -> T | None:
        items = self._items.value
        if 0 <= idx < len(items):
            return items[idx]
        return None

    def dispose(self) -> None:
        self._loader.cancel()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
