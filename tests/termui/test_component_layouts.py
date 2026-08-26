# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_component_layouts.py
Description: Unit tests for layout container components (Column/Row).
Author: Zev
Date: 2026-04-20
"""

import pytest

from pigit.termui.component import Component
from pigit.termui.containers import Column, Row
from pigit.termui.types import EventType


def _make_component(name: str = "mock") -> Component:
    """Return a concrete Component subclass with the given NAME."""
    return type(name, (Component,), {"NAME": name, "refresh": lambda self: None})()


@pytest.fixture(params=["column", "row"], ids=["column", "row"])
def container_factory(request):
    """Return a builder that sizes children along the container's own axis."""

    def build(children, spec):
        if request.param == "column":
            return Column(children, heights=spec)
        return Row(children, widths=spec)

    return build


def test_accept_skips_non_callable(container_factory):
    class NoAccept(Component):
        NAME = "no_accept"

    c1 = NoAccept()
    container = container_factory([c1], [1])
    container.accept(EventType("action_requested"), foo="bar")
    assert container.children == [c1]


def test_accept_broadcasts(container_factory):
    class Acceptable(Component):
        NAME = "acc"

        def __init__(self):
            super().__init__()
            self.received = []

        def accept(self, action, **data):
            self.received.append((action, data))

    a1 = Acceptable()
    a2 = Acceptable()
    container = container_factory([a1, a2], [1, 1])
    container.accept(EventType("action_requested"), key="v")
    assert a1.received == [(EventType("action_requested"), {"key": "v"})]
    assert a2.received == [(EventType("action_requested"), {"key": "v"})]


def test_render_skips_zero_size(container_factory):
    from pigit.termui.surface import Surface

    c1 = _make_component()
    c2 = _make_component()
    container = container_factory([c1, c2], [0, 1])
    container.resize((10, 1))
    container.paint(Surface(10, 1))


def test_render_skips_negative_position(container_factory):
    from pigit.termui.surface import Surface

    c1 = _make_component()
    container = container_factory([c1], [1])
    container.resize((10, 1))
    c1.x = 0
    container.paint(Surface(10, 1))


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

    def test_set_widths_lays_out_replaced_child(self):
        """Same width spec must still size a child that was swapped in."""
        c1 = _make_component()
        c2 = _make_component()
        row = Row([c1, c2], widths=[3, 7])
        row.resize((10, 5))
        c3 = _make_component()
        row.children[1] = c3
        c3.parent = row
        row.set_widths([3, 7])
        assert c3._size == (7, 5)
