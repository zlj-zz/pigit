# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_layout.py
Description: Tests for the lightweight layout system.
Author: Zev
Date: 2026-04-17
"""

from pigit.termui._layout import Padding, Border, layout_flex


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


class TestLayoutFlex:
    def test_all_fixed(self):
        assert layout_flex([3, 2], 10) == [3, 2]

    def test_one_flex(self):
        assert layout_flex([2, "flex"], 10) == [2, 8]

    def test_two_flex_even(self):
        assert layout_flex(["flex", "flex"], 10) == [5, 5]

    def test_remainder_goes_to_last_flex(self):
        assert layout_flex(["flex", "flex"], 11) == [5, 6]

    def test_fixed_plus_flex_remainder(self):
        assert layout_flex([3, "flex", "flex"], 13) == [3, 5, 5]
        assert layout_flex([3, "flex", "flex"], 14) == [3, 5, 6]

    def test_clamps_fixed_to_remaining(self):
        assert layout_flex([8, 5], 10) == [8, 2]
