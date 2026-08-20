"""
Module: pigit/viewmodels/base.py
Description: ViewModel base class and shared abstractions.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

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

    @property
    def items(self) -> Signal[list[T]]:
        return self._items

    def refresh(self) -> None:
        self._loader.start(self._do_load, self._on_loaded)

    def _do_load(self) -> list[T]:
        """Override to perform the actual data fetch."""
        raise NotImplementedError

    def _on_loaded(self, data: list[T]) -> None:
        self._items.set(data)
        # A fresh load may have changed the underlying git state, so any
        # memoized inspector snapshot is stale.
        self._inspector_key = self._NO_SNAPSHOT
        self._inspector_value = None

    def _memo_inspector(self, key: object, build: Callable[[], _S | None]) -> _S | None:
        """Return a memoized inspector snapshot for *key*.

        Reopening the inspector on an unchanged selection reuses the previous
        snapshot instead of re-running git reads. Any refresh invalidates it
        via :meth:`_on_loaded`.
        """
        if self._inspector_key == key:
            return cast(_S | None, self._inspector_value)
        value = build()
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
