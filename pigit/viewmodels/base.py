"""
Module: pigit/viewmodels/base.py
Description: ViewModel base class and shared abstractions.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar, runtime_checkable
from collections.abc import Callable

from pigit.termui._async_task import AsyncTask
from pigit.termui.reactive import Signal

T = TypeVar("T")


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

    def __init__(self) -> None:
        self._loader = AsyncTask()
        self._items: Signal[list[T]] = Signal([])
        self._unsubs: list[Callable[[], None]] = []

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

    def dispose(self) -> None:
        self._loader.cancel()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
