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
    """Result of a ViewModel action. Panel decides whether to refresh."""

    success: bool
    message: str = ""
    should_refresh: bool = False


@runtime_checkable
class IListViewModel(Protocol, Generic[T]):
    """Protocol for list-based panel ViewModels."""

    @property
    def items(self) -> Signal[list[T]]:
        """Current list of items. Panel subscribes via bind_signals()."""
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

    def __init__(self) -> None:
        self._loader = AsyncTask()
        self._items: Signal[list[T]] = Signal([])
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

    def bind_repo_token(self, token: object | None) -> None:
        """Point this VM at the app's current repo generation token."""
        self._repo_token = token

    def refresh(self) -> None:
        self._loader.start(self._do_load, self._guarded(self._on_loaded))

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
        # A fresh load may have changed the underlying git state, so any
        # memoized inspector snapshot is stale.
        with self._inspector_lock:
            self._inspector_key = self._NO_SNAPSHOT
            self._inspector_value = None

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
