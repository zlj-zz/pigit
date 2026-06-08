"""
Module: tests/termui/test_reactive_weakref.py
Description: Tests for weak-reference Signal subscriptions (bound methods only).
Author: Zev
Date: 2026-06-08
"""

from __future__ import annotations

import gc
import weakref

import pytest

from pigit.termui.reactive import Signal, Computed


def test_signal_drops_dead_bound_method():
    """Bound method subscriber GC'd → Signal no longer holds it."""
    sig = Signal(0)

    class Target:
        def __init__(self):
            self.calls = []

        def on_change(self, v):
            self.calls.append(v)

    target = Target()
    sig.subscribe(target.on_change)
    sig.set(1)
    assert target.calls == [1]

    del target
    gc.collect()
    gc.collect()

    sig.set(2)
    assert all(r() is None for r in sig._subs)


def test_non_bound_method_rejected():
    """Lambda and plain functions are rejected by subscribe()."""
    sig = Signal(0)

    with pytest.raises(TypeError):
        sig.subscribe(lambda v: print(v))

    def plain(v):
        pass

    with pytest.raises(TypeError):
        sig.subscribe(plain)


def test_computed_reactive_drops_dep_subscriber():
    """Computed GC'd → its dep subscriptions auto-clean."""
    dep = Signal(0)
    c = Computed(lambda: dep.value * 2, deps=[dep])
    dep.set(1)
    assert c.value == 2

    del c
    gc.collect()
    gc.collect()

    dep.set(2)
    assert all(r() is None for r in dep._subs)


def test_unsubscribe_after_gc_is_safe():
    """Calling unsub after target GC'd does not crash."""
    sig = Signal(0)

    class Target:
        def on_change(self, v):
            pass

    target = Target()
    unsub = sig.subscribe(target.on_change)
    del target
    gc.collect()

    unsub()


def test_lazy_cleanup_on_set():
    """Dead refs are removed during set(), not immediately."""
    sig = Signal(0)

    class Target:
        def on_change(self, v):
            pass

    t1 = Target()
    t2 = Target()
    sig.subscribe(t1.on_change)
    sig.subscribe(t2.on_change)
    assert len(sig._subs) == 2

    del t1
    gc.collect()
    assert len(sig._subs) == 2

    sig.set(1)
    assert len(sig._subs) == 1


def test_signal_unsub_does_not_prevent_gc():
    """unsub lambda should not strongly reference Signal."""
    sig = Signal(0)
    sig_ref = weakref.ref(sig)

    class Target:
        def on_change(self, v):
            pass

    target = Target()
    unsub = sig.subscribe(target.on_change)

    del sig
    gc.collect()
    gc.collect()

    assert sig_ref() is None


def test_computed_lazy_mode_subscriber_cleanup():
    """Computed lazy mode subscribers are cleaned when Computed is GC'd."""
    sig = Signal(0)
    c = Computed(lambda: sig.value + 1)
    c.value

    class Target:
        def on_change(self, v):
            pass

    target = Target()
    c.subscribe(target.on_change)

    del c
    gc.collect()
    gc.collect()

    sig.set(1)
    assert all(r() is None for r in sig._subs)
