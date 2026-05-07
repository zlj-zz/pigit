"""
Module: pigit/termui/_reactive.py
Description: Lightweight reactive primitives: Signal and Computed.
Author: Zev
Date: 2026-04-20
"""

from __future__ import annotations

from typing import Generic, TypeAlias, TypeVar
from collections.abc import Callable

T = TypeVar("T")


class Signal(Generic[T]):
    """Reactive value. Subscribers are notified on every write."""

    def __init__(self, value: T) -> None:
        self._value = value
        self._subs: list[Callable[[T], None]] = []

    @property
    def value(self) -> T:
        """Return the current value of the signal."""
        return self._value

    def set(self, value: T) -> None:
        """Set the value and notify subscribers if it changed."""
        if value == self._value:
            return
        self._value = value
        for cb in self._subs:
            cb(value)

    def subscribe(self, callback: Callable[[T], None]) -> Callable[[], None]:
        """Subscribe to value changes. Returns an unsubscribe function."""
        self._subs.append(callback)
        return lambda: self._subs.remove(callback)


class Computed(Generic[T]):
    """Derived signal.  Two modes:

    - **Lazy mode** (``deps`` is *None*, default): recompute on every
      ``.value`` read; notify subscribers when the result changes.
    - **Reactive mode** (``deps`` is a list): subscribe to the given Signals
      and recompute automatically when any dependency changes.  ``.value``
      returns the cached result.
    """

    def __init__(
        self,
        fn: Callable[[], T],
        deps: list[Signal] | None = None,
    ) -> None:
        self._fn = fn
        self.deps = deps
        self._value: T = fn()

        if deps is not None:
            # Reactive mode: subscribe to deps
            self._subs: list[Callable[[T], None]] = []
            self._unsubs: list[Callable[[], None]] = []
            for dep in deps:
                self._unsubs.append(dep.subscribe(lambda _: self._recompute()))
        else:
            # Lazy mode: backwards-compatible, recompute on each .value read
            self._signal = Signal(self._value)

    def _recompute(self) -> None:
        new = self._fn()
        if new != self._value:
            self._value = new
            for cb in self._subs:
                cb(new)

    @property
    def value(self) -> T:
        if self.deps is not None:
            return self._value
        # Lazy mode: recompute and notify on each read
        new = self._fn()
        if new != self._value:
            self._value = new
            self._signal.set(new)
        return self._value

    def subscribe(self, callback: Callable[[T], None]) -> Callable[[], None]:
        if self.deps is not None:
            self._subs.append(callback)
            return lambda: self._subs.remove(callback)
        return self._signal.subscribe(callback)


# Type alias for component props that accept both static and reactive data.
ValueRef: TypeAlias = T | Signal[T] | Computed[T]
