# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_layout.py
Description: Tests for the lightweight layout system.
Author: Zev
Date: 2026-04-17
"""

import pytest

from pigit.termui.layout import Padding, Border, FlexRow, FlexColumn
from pigit.termui.components import Component


class _Leaf(Component):
    NAME = "leaf"

    def __init__(self):
        super().__init__()
        self.resized = []

    def resize(self, size):
        self.resized.append(size)
        super().resize(size)

    def fresh(self):
        pass


class TestPadding:
    def test_apply(self):
        p = Padding(top=1, right=2, bottom=1, left=2)
        assert p.apply((10, 8)) == (6, 6)

    def test_never_negative(self):
        p = Padding(top=5, bottom=5)
        assert p.apply((4, 4)) == (4, 0)

    def test_offset(self):
        p = Padding(top=1, right=2, bottom=3, left=4)
        assert p.offset() == (1, 4)


class TestBorder:
    def test_apply(self):
        b = Border()
        assert b.apply((10, 6)) == (8, 4)

    def test_never_negative(self):
        b = Border()
        assert b.apply((1, 1)) == (0, 0)

    def test_offset(self):
        b = Border()
        assert b.offset() == (1, 1)


class TestFlexRow:
    def test_equal_flex(self):
        a, b = _Leaf(), _Leaf()
        row = FlexRow([a, b], [1, 1])
        row.resize_children((10, 5), offset=(1, 1))
        assert a._size == (5, 5)
        assert b._size == (5, 5)

    def test_unequal_flex(self):
        a, b = _Leaf(), _Leaf()
        row = FlexRow([a, b], [1, 2])
        row.resize_children((12, 4), offset=(1, 1))
        assert a._size == (4, 4)
        assert b._size == (8, 4)

    def test_sum_equals_total_width(self):
        a, b, c = _Leaf(), _Leaf(), _Leaf()
        row = FlexRow([a, b, c], [1, 1, 1])
        row.resize_children((10, 3), offset=(1, 1))
        total = a._size[0] + b._size[0] + c._size[0]
        assert total == 10

    def test_offset_applied_to_coords(self):
        a = _Leaf()
        row = FlexRow([a], [1])
        row.resize_children((6, 4), offset=(3, 5))
        assert a.x == 3
        assert a.y == 5

    def test_total_flex_zero_raises(self):
        a = _Leaf()
        row = FlexRow([a], [0])
        with pytest.raises(ValueError, match="total_flex must be > 0"):
            row.resize_children((10, 5), offset=(1, 1))

    def test_insufficient_width_raises(self):
        a, b, c = _Leaf(), _Leaf(), _Leaf()
        row = FlexRow([a, b, c], [1, 1, 1])
        with pytest.raises(ValueError, match="available width 2 is smaller"):
            row.resize_children((2, 5), offset=(1, 1))

    def test_flexes_length_mismatch_raises(self):
        a, b = _Leaf(), _Leaf()
        with pytest.raises(ValueError, match="flexes length must match"):
            FlexRow([a, b], [1])


class TestFlexColumn:
    def test_equal_flex(self):
        a, b = _Leaf(), _Leaf()
        col = FlexColumn([a, b], [1, 1])
        col.resize_children((8, 10), offset=(1, 1))
        assert a._size == (8, 5)
        assert b._size == (8, 5)

    def test_sum_equals_total_height(self):
        a, b, c = _Leaf(), _Leaf(), _Leaf()
        col = FlexColumn([a, b, c], [1, 1, 1])
        col.resize_children((4, 10), offset=(1, 1))
        total = a._size[1] + b._size[1] + c._size[1]
        assert total == 10

    def test_offset_applied_to_coords(self):
        a = _Leaf()
        col = FlexColumn([a], [1])
        col.resize_children((6, 4), offset=(2, 4))
        assert a.x == 2
        assert a.y == 4

    def test_total_flex_zero_raises(self):
        a = _Leaf()
        col = FlexColumn([a], [0])
        with pytest.raises(ValueError, match="total_flex must be > 0"):
            col.resize_children((10, 5), offset=(1, 1))

    def test_insufficient_height_raises(self):
        a, b, c = _Leaf(), _Leaf(), _Leaf()
        col = FlexColumn([a, b, c], [1, 1, 1])
        with pytest.raises(ValueError, match="available height 2 is smaller"):
            col.resize_children((4, 2), offset=(1, 1))

    def test_flexes_length_mismatch_raises(self):
        a, b = _Leaf(), _Leaf()
        with pytest.raises(ValueError, match="flexes length must match"):
            FlexColumn([a, b], [1])
