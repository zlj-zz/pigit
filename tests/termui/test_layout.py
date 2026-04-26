# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_layout.py
Description: Tests for the lightweight layout system.
Author: Zev
Date: 2026-04-17
"""

import pytest

from pigit.termui._layout import Padding, Border


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
