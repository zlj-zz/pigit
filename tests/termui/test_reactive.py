# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_reactive.py
Description: Unit tests for Signal and Computed reactive primitives.
Author: Zev
Date: 2026-04-20
"""

import pytest

from pigit.termui.reactive import Computed, Signal


class _Subscriber:
    def __init__(self):
        self.calls = []

    def on_change(self, v):
        self.calls.append(v)


class TestSignal:
    def test_initial_value(self):
        s = Signal(42)
        assert s.value == 42

    def test_set_updates_value(self):
        s = Signal(0)
        s.set(5)
        assert s.value == 5

    def test_subscriber_notified(self):
        s = Signal(0)
        sub = _Subscriber()
        s.subscribe(sub.on_change)
        s.set(1)
        s.set(2)
        assert sub.calls == [1, 2]

    def test_no_notification_on_same_value(self):
        s = Signal(0)
        sub = _Subscriber()
        s.subscribe(sub.on_change)
        s.set(0)
        assert sub.calls == []

    def test_unsubscribe(self):
        s = Signal(0)
        sub = _Subscriber()
        unsub = s.subscribe(sub.on_change)
        unsub()
        s.set(1)
        assert sub.calls == []

    def test_multiple_subscribers(self):
        s = Signal(0)
        a, b = _Subscriber(), _Subscriber()
        s.subscribe(a.on_change)
        s.subscribe(b.on_change)
        s.set(1)
        assert a.calls == [1]
        assert b.calls == [1]


class TestComputed:
    def test_initial_value(self):
        c = Computed(lambda: 10)
        assert c.value == 10

    def test_recomputes_on_each_read(self):
        call_count = [0]

        def fn():
            call_count[0] += 1
            return 42

        c = Computed(fn)
        _ = c.value  # init + first read = 2 calls
        _ = c.value  # second read = 1 more call
        assert call_count[0] == 3  # init + 2 reads

    def test_subscriber_notified_on_change(self):
        base = Signal(1)
        c = Computed(lambda: base.value * 2)
        sub = _Subscriber()
        c.subscribe(sub.on_change)

        base.set(2)  # computed now 4
        _ = c.value  # trigger recompute + notify
        assert sub.calls == [4]

    def test_no_notification_when_unchanged(self):
        base = Signal(1)
        c = Computed(lambda: base.value % 2)
        sub = _Subscriber()
        c.subscribe(sub.on_change)

        base.set(3)  # 3 % 2 == 1, same as before
        _ = c.value
        assert sub.calls == []

    def test_unsubscribe(self):
        base = Signal(1)
        c = Computed(lambda: base.value)
        sub = _Subscriber()
        unsub = c.subscribe(sub.on_change)
        unsub()
        base.set(2)
        _ = c.value
        assert sub.calls == []


class TestComputedReactiveMode:
    def test_initial_value_with_deps(self):
        base = Signal(10)
        c = Computed(lambda: base.value * 2, deps=[base])
        assert c.value == 20

    def test_recomputes_when_dep_changes(self):
        base = Signal(1)
        c = Computed(lambda: base.value + 1, deps=[base])
        base.set(5)
        assert c.value == 6

    def test_subscriber_notified_when_dep_changes(self):
        base = Signal(1)
        c = Computed(lambda: base.value * 3, deps=[base])
        sub = _Subscriber()
        c.subscribe(sub.on_change)
        base.set(2)
        assert sub.calls == [6]

    def test_no_notification_when_unchanged(self):
        base = Signal(1)
        c = Computed(lambda: base.value % 2, deps=[base])
        sub = _Subscriber()
        c.subscribe(sub.on_change)
        base.set(3)
        assert sub.calls == []

    def test_unsubscribe_removes_listener(self):
        base = Signal(1)
        c = Computed(lambda: base.value, deps=[base])
        sub = _Subscriber()
        unsub = c.subscribe(sub.on_change)
        unsub()
        base.set(2)
        assert sub.calls == []

    def test_multiple_deps(self):
        a = Signal(1)
        b = Signal(2)
        c = Computed(lambda: a.value + b.value, deps=[a, b])
        sub = _Subscriber()
        c.subscribe(sub.on_change)
        a.set(10)
        assert sub.calls == [12]
        b.set(20)
        assert sub.calls == [12, 30]
