# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_reactive.py
Description: Unit tests for Signal and Computed reactive primitives.
Author: Zev
Date: 2026-04-20
"""

import pytest

from pigit.termui.reactive import Computed, Signal


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
        called = []
        s.subscribe(lambda v: called.append(v))
        s.set(1)
        s.set(2)
        assert called == [1, 2]

    def test_no_notification_on_same_value(self):
        s = Signal(0)
        called = []
        s.subscribe(lambda v: called.append(v))
        s.set(0)
        assert called == []

    def test_unsubscribe(self):
        s = Signal(0)
        called = []
        unsub = s.subscribe(lambda v: called.append(v))
        unsub()
        s.set(1)
        assert called == []

    def test_multiple_subscribers(self):
        s = Signal(0)
        a, b = [], []
        s.subscribe(lambda v: a.append(v))
        s.subscribe(lambda v: b.append(v))
        s.set(1)
        assert a == [1]
        assert b == [1]


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
        called = []
        c.subscribe(lambda v: called.append(v))

        base.set(2)  # computed now 4
        _ = c.value  # trigger recompute + notify
        assert called == [4]

    def test_no_notification_when_unchanged(self):
        base = Signal(1)
        c = Computed(lambda: base.value % 2)
        called = []
        c.subscribe(lambda v: called.append(v))

        base.set(3)  # 3 % 2 == 1, same as before
        _ = c.value
        assert called == []

    def test_unsubscribe(self):
        base = Signal(1)
        c = Computed(lambda: base.value)
        called = []
        unsub = c.subscribe(lambda v: called.append(v))
        unsub()
        base.set(2)
        _ = c.value
        assert called == []


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
        called = []
        c.subscribe(lambda v: called.append(v))
        base.set(2)
        assert called == [6]

    def test_no_notification_when_unchanged(self):
        base = Signal(1)
        c = Computed(lambda: base.value % 2, deps=[base])
        called = []
        c.subscribe(lambda v: called.append(v))
        base.set(3)
        assert called == []

    def test_unsubscribe_removes_listener(self):
        base = Signal(1)
        c = Computed(lambda: base.value, deps=[base])
        called = []
        unsub = c.subscribe(lambda v: called.append(v))
        unsub()
        base.set(2)
        assert called == []

    def test_multiple_deps(self):
        a = Signal(1)
        b = Signal(2)
        c = Computed(lambda: a.value + b.value, deps=[a, b])
        called = []
        c.subscribe(lambda v: called.append(v))
        a.set(10)
        assert called == [12]
        b.set(20)
        assert called == [12, 30]
