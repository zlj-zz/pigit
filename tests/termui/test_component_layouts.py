# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_component_layouts.py
Description: Unit tests for layout container components (Column).
Author: Zev
Date: 2026-04-20
"""

import pytest

from pigit.termui._component import Component
from pigit.termui.containers import Column, Row
from pigit.termui.types import ActionEventType


def _make_component(name: str = "mock") -> Component:
    """Return a concrete Component subclass with the given NAME."""
    return type(name, (Component,), {"NAME": name, "refresh": lambda self: None})()


class TestColumn:
    def test_set_heights_mismatch(self):
        c1 = _make_component()
        c2 = _make_component()
        col = Column([c1, c2], heights=[1, "flex"])
        with pytest.raises(ValueError):
            col.set_heights([1])

    def test_resize_fixed(self):
        c1 = _make_component()
        c2 = _make_component()
        col = Column([c1, c2], heights=[3, 2])
        col.resize((10, 5))
        assert col._size == (10, 5)
        assert c1._size == (10, 3)
        assert c2._size == (10, 2)

    def test_resize_flex(self):
        c1 = _make_component()
        c2 = _make_component()
        col = Column([c1, c2], heights=[2, "flex"])
        col.resize((10, 10))
        assert c1._size == (10, 2)
        assert c2._size == (10, 8)

    def test_resize_overflow(self):
        c1 = _make_component()
        c2 = _make_component()
        col = Column([c1, c2], heights=[10, 5])
        col.resize((10, 8))
        assert c1._size[1] == 8
        assert c2._size[1] == 0

    def test_child_positions(self):
        c1 = _make_component()
        c2 = _make_component()
        col = Column([c1, c2], heights=[2, 3], x=1, y=1)
        col.resize((10, 5))
        assert (c1.x, c1.y) == (1, 1)
        assert (c2.x, c2.y) == (3, 1)

    def test_destroy_propagates(self):
        class MockChild(Component):
            NAME = "mock_child"

            def __init__(self):
                super().__init__()
                self.destroyed = False

            def destroy(self):
                self.destroyed = True

        c1 = MockChild()
        c2 = MockChild()
        col = Column([c1, c2], heights=[1, 1])
        col.destroy()
        assert c1.destroyed
        assert c2.destroyed

    def test_set_heights_no_change(self):
        c1 = _make_component()
        c2 = _make_component()
        col = Column([c1, c2], heights=[1, "flex"])
        col.resize((10, 5))
        col.set_heights([1, "flex"])
        assert col._heights == [1, "flex"]

    def test_set_heights_triggers_resize(self):
        c1 = _make_component()
        c2 = _make_component()
        col = Column([c1, c2], heights=[1, "flex"])
        col.resize((10, 10))
        assert c1._size == (10, 1)
        col.set_heights([5, "flex"])
        assert c1._size == (10, 5)

    def test_render_skips_zero_size(self):
        from pigit.termui._surface import Surface

        c1 = _make_component()
        c2 = _make_component()
        col = Column([c1, c2], heights=[0, 1])
        col.resize((10, 1))
        s = Surface(10, 1)
        col._render_surface(s)

    def test_render_skips_negative_position(self):
        from pigit.termui._surface import Surface

        c1 = _make_component()
        col = Column([c1], heights=[1])
        col.resize((10, 1))
        c1.x = 0
        s = Surface(10, 1)
        col._render_surface(s)

    def test_accept_skips_non_callable(self):
        class NoAccept(Component):
            NAME = "no_accept"

        c1 = NoAccept()
        col = Column([c1], heights=[1])
        col.accept(ActionEventType.action_requested, foo="bar")
        assert col.children == [c1]

    def test_accept_broadcasts(self):
        class Acceptable(Component):
            NAME = "acc"

            def __init__(self):
                super().__init__()
                self.received = []

            def accept(self, action, **data):
                self.received.append((action, data))

        a1 = Acceptable()
        a2 = Acceptable()
        col = Column([a1, a2], heights=[1, 1])
        col.accept(ActionEventType.action_requested, key="v")
        assert a1.received == [(ActionEventType.action_requested, {"key": "v"})]
        assert a2.received == [(ActionEventType.action_requested, {"key": "v"})]


class TestRow:
    def test_set_widths_mismatch(self):
        c1 = _make_component()
        c2 = _make_component()
        row = Row([c1, c2], widths=[1, "flex"])
        with pytest.raises(ValueError):
            row.set_widths([1])

    def test_resize_fixed(self):
        c1 = _make_component()
        c2 = _make_component()
        row = Row([c1, c2], widths=[3, 2])
        row.resize((5, 10))
        assert row._size == (5, 10)
        assert c1._size == (3, 10)
        assert c2._size == (2, 10)

    def test_resize_flex(self):
        c1 = _make_component()
        c2 = _make_component()
        row = Row([c1, c2], widths=[2, "flex"])
        row.resize((10, 10))
        assert c1._size == (2, 10)
        assert c2._size == (8, 10)

    def test_child_positions(self):
        c1 = _make_component()
        c2 = _make_component()
        row = Row([c1, c2], widths=[2, 3], x=1, y=1)
        row.resize((10, 5))
        assert (c1.x, c1.y) == (1, 1)
        assert (c2.x, c2.y) == (1, 3)

    def test_set_widths_no_change(self):
        c1 = _make_component()
        c2 = _make_component()
        row = Row([c1, c2], widths=[1, "flex"])
        row.resize((10, 5))
        row.set_widths([1, "flex"])
        assert row._widths == [1, "flex"]

    def test_set_widths_triggers_resize(self):
        c1 = _make_component()
        c2 = _make_component()
        row = Row([c1, c2], widths=[1, "flex"])
        row.resize((10, 10))
        assert c1._size == (1, 10)
        row.set_widths([5, "flex"])
        assert c1._size == (5, 10)

    def test_render_skips_zero_size(self):
        from pigit.termui._surface import Surface

        c1 = _make_component()
        c2 = _make_component()
        row = Row([c1, c2], widths=[0, 1])
        row.resize((1, 10))
        s = Surface(1, 10)
        row._render_surface(s)

    def test_render_skips_negative_position(self):
        from pigit.termui._surface import Surface

        c1 = _make_component()
        row = Row([c1], widths=[1])
        row.resize((1, 10))
        c1.x = 0
        s = Surface(1, 10)
        row._render_surface(s)

    def test_accept_skips_non_callable(self):
        class NoAccept(Component):
            NAME = "no_accept"

        c1 = NoAccept()
        row = Row([c1], widths=[1])
        row.accept(ActionEventType.action_requested, foo="bar")
        assert row.children == [c1]

    def test_accept_broadcasts(self):
        class Acceptable(Component):
            NAME = "acc"

            def __init__(self):
                super().__init__()
                self.received = []

            def accept(self, action, **data):
                self.received.append((action, data))

        a1 = Acceptable()
        a2 = Acceptable()
        row = Row([a1, a2], widths=[1, 1])
        row.resize((2, 1))
        row.accept(ActionEventType.action_requested, key="v")
        assert a1.received == [(ActionEventType.action_requested, {"key": "v"})]
        assert a2.received == [(ActionEventType.action_requested, {"key": "v"})]
