# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_component_layouts.py
Description: Unit tests for layout container components (Column).
Author: Zev
Date: 2026-04-20
"""

import pytest

from pigit.termui._component_base import Component
from pigit.termui._component_layouts import Column


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
        # x=row, y=col; c1 at row 1 col 1, c2 stacked below at row 3 col 1
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
