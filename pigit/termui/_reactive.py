# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_reactive.py
Description: Lightweight reactive primitives: Signal and Computed.
Author: Zev
Date: 2026-04-20
"""

from __future__ import annotations

from typing import Callable, Generic, TypeVar

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
    """Derived signal. Cached; only notifies subscribers when value actually changes."""

    def __init__(self, fn: Callable[[], T]) -> None:
        self._fn = fn
        self._value: T = fn()
        self._signal = Signal(self._value)

    @property
    def value(self) -> T:
        """Return the current derived value, recomputing and notifying if changed."""
        new = self._fn()
        if new != self._value:
            self._value = new
            self._signal.set(new)
        return self._value

    def subscribe(self, callback: Callable[[T], None]) -> Callable[[], None]:
        """Proxy to underlying signal so callers can observe derived value changes."""
        return self._signal.subscribe(callback)
