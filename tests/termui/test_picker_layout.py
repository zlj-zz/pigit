# -*- coding: utf-8 -*-
"""Tests for pigit.termui.picker_layout viewport helpers."""

from __future__ import annotations

from pigit.termui.picker_layout import picker_terminal_ok, picker_viewport


class TestPickerViewport:
    def test_calculates_available_list_rows(self):
        # Header (3) + Footer (2) = 5 fixed rows
        assert picker_viewport(10) == 5
        assert picker_viewport(20) == 15

    def test_small_terminal(self):
        assert picker_viewport(5) == 0


class TestPickerTerminalOk:
    def test_large_enough(self):
        assert picker_terminal_ok(20) is True

    def test_too_small(self):
        assert picker_terminal_ok(5) is False
