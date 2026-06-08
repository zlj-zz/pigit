"""
Module: pigit/termui/reactive.py
Description: Lightweight reactive primitives: Signal and Computed.
Author: Zev
Date: 2026-04-20
"""

from __future__ import annotations

import inspect
import weakref
from typing import Generic, TypeAlias, TypeVar
from collections.abc import Callable

T = TypeVar("T")


class Signal(Generic[T]):
    """Reactive value. Subscribers are notified on every write.

    ``subscribe()`` only accepts **bound methods**. This ensures that when the
    owning instance is garbage-collected, the subscription is automatically
    dropped without requiring an explicit unsubscribe call.
    """

    def __init__(self, value: T) -> None:
        self._value = value
        self._subs: list[weakref.ref] = []

    @property
    def value(self) -> T:
        """Return the current value of the signal."""
        return self._value

    def set(self, value: T) -> None:
        """Set the value and notify subscribers if it changed."""
        if value == self._value:
            return
        self._value = value
        cbs: list[Callable[[T], None]] = []
        alive: list[weakref.ref] = []
        for ref in self._subs:
            cb = ref()
            if cb is not None:
                cbs.append(cb)
                alive.append(ref)
        self._subs = alive
        for cb in cbs:
            cb(value)

    def subscribe(self, callback: Callable[[T], None]) -> Callable[[], None]:
        """Subscribe to value changes. Returns an unsubscribe function.

        Raises:
            TypeError: If ``callback`` is not a bound method.
        """
        if not inspect.ismethod(callback):
            raise TypeError(
                "Signal.subscribe() requires a bound method. "
                "Pass a method on your component (e.g. self._on_change), "
                "not a lambda or plain function."
            )
        ref = weakref.WeakMethod(callback)
        self._subs.append(ref)
        self_ref = weakref.ref(self)

        def _unsub() -> None:
            s = self_ref()
            if s is not None:
                s._unsubscribe(ref)

        return _unsub

    def _unsubscribe(self, ref: weakref.ref) -> None:
        try:
            self._subs.remove(ref)
        except ValueError:
            pass


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
            self._subs: list[weakref.ref] = []
            for dep in deps:
                dep.subscribe(self._on_dep_change)
        else:
            self._signal = Signal(self._value)

    def _on_dep_change(self, _: T) -> None:
        """Handler subscribed to each dependency Signal."""
        self._recompute()

    def _recompute(self) -> None:
        new = self._fn()
        if new != self._value:
            self._value = new
            cbs: list[Callable[[T], None]] = []
            alive: list[weakref.ref] = []
            for ref in self._subs:
                cb = ref()
                if cb is not None:
                    cbs.append(cb)
                    alive.append(ref)
            self._subs = alive
            for cb in cbs:
                cb(new)

    @property
    def value(self) -> T:
        if self.deps is not None:
            return self._value
        new = self._fn()
        if new != self._value:
            self._value = new
            self._signal.set(new)
        return self._value

    def subscribe(self, callback: Callable[[T], None]) -> Callable[[], None]:
        if self.deps is not None:
            if not inspect.ismethod(callback):
                raise TypeError(
                    "Computed.subscribe() requires a bound method. "
                    "Pass a method on your component, not a lambda or plain function."
                )
            ref = weakref.WeakMethod(callback)
            self._subs.append(ref)
            self_ref = weakref.ref(self)

            def _unsub() -> None:
                c = self_ref()
                if c is not None:
                    c._unsubscribe(ref)

            return _unsub
        return self._signal.subscribe(callback)

    def _unsubscribe(self, ref: weakref.ref) -> None:
        try:
            self._subs.remove(ref)
        except ValueError:
            pass


# Type alias for component props that accept both static and reactive data.
ValueRef: TypeAlias = T | Signal[T] | Computed[T]
