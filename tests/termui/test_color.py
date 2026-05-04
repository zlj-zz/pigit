# -*- coding: utf-8 -*-
"""Tests for pigit.termui._color."""

from __future__ import annotations

import os
from unittest import mock

import pytest

from pigit.termui._color import (
    ColorAdapter,
    ColorMode,
    _nearest_16,
    _nearest_256,
)


class TestColorMode:
    def test_enum_values(self):
        assert ColorMode.TRUECOLOR.value == "truecolor"
        assert ColorMode.COLOR_256.value == "256"
        assert ColorMode.COLOR_16.value == "16"
        assert ColorMode.NONE.value == "none"


class TestColorAdapter:
    def test_truecolor_fg_sequence(self):
        adapter = ColorAdapter(ColorMode.TRUECOLOR)
        seq = adapter.fg_sequence((255, 0, 0))
        assert seq == "\033[38;2;255;0;0m"

    def test_truecolor_bg_sequence(self):
        adapter = ColorAdapter(ColorMode.TRUECOLOR)
        seq = adapter.bg_sequence((0, 0, 255))
        assert seq == "\033[48;2;0;0;255m"

    def test_style_sequence(self):
        from pigit.termui.palette import STYLE_BOLD, STYLE_DIM, STYLE_ITALIC

        adapter = ColorAdapter(ColorMode.TRUECOLOR)
        assert adapter.style_sequence(STYLE_BOLD) == "\033[1m"
        assert adapter.style_sequence(STYLE_DIM) == "\033[2m"
        assert adapter.style_sequence(STYLE_ITALIC) == "\033[3m"
        assert adapter.style_sequence(STYLE_BOLD | STYLE_DIM) == "\033[1;2m"
        assert adapter.style_sequence(0) == ""

    def test_reset_style_sequence(self):
        adapter = ColorAdapter(ColorMode.TRUECOLOR)
        assert adapter.reset_style_sequence() == "\033[22;23;24;27m"

    def test_reset_sequence(self):
        adapter = ColorAdapter(ColorMode.TRUECOLOR)
        assert adapter.reset_sequence() == "\033[0m"

    def test_none_mode_returns_empty(self):
        adapter = ColorAdapter(ColorMode.NONE)
        assert adapter.fg_sequence((255, 0, 0)) == ""
        assert adapter.bg_sequence((0, 0, 255)) == ""

    def test_256_mode_returns_38_5_code(self):
        adapter = ColorAdapter(ColorMode.COLOR_256)
        seq = adapter.fg_sequence((255, 0, 0))
        assert seq == "\033[38;5;9m"

    def test_16_mode_returns_bright_red_code(self):
        adapter = ColorAdapter(ColorMode.COLOR_16)
        seq = adapter.fg_sequence((255, 0, 0))
        # Code 9 (bright red) maps to 91
        assert seq == "\033[91m"


class TestNearest256:
    def test_exact_black(self):
        assert _nearest_256((0, 0, 0)) == 0

    def test_exact_white(self):
        # White is in the 16-color palette (code 15)
        assert _nearest_256((255, 255, 255)) == 15

    def test_exact_red(self):
        # Pure red is in the 16-color palette (code 9)
        assert _nearest_256((255, 0, 0)) == 9

    def test_gray(self):
        # Mid-gray (128,128,128) is bright black in 16-color palette (code 8)
        code = _nearest_256((128, 128, 128))
        assert code == 8

    def test_caching(self):
        # Second call should use cache
        result1 = _nearest_256((100, 150, 200))
        result2 = _nearest_256((100, 150, 200))
        assert result1 == result2


class TestNearest16:
    def test_exact_black(self):
        assert _nearest_16((0, 0, 0)) == 0

    def test_exact_red(self):
        assert _nearest_16((255, 0, 0)) == 9

    def test_exact_white(self):
        assert _nearest_16((255, 255, 255)) == 15


class TestDetectColorMode:
    def test_force_env_var(self):
        with mock.patch.dict(os.environ, {"PIGIT_COLOR_MODE": "16"}):
            adapter = ColorAdapter()
            assert adapter.mode == ColorMode.COLOR_16

    def test_truecolor_from_colorterm(self):
        with mock.patch.dict(
            os.environ,
            {"COLORTERM": "truecolor", "PIGIT_COLOR_MODE": ""},
        ):
            adapter = ColorAdapter()
            assert adapter.mode == ColorMode.TRUECOLOR

    def test_256_from_term(self):
        with mock.patch.dict(
            os.environ,
            {"TERM": "xterm-256color", "COLORTERM": "", "PIGIT_COLOR_MODE": ""},
        ):
            adapter = ColorAdapter()
            assert adapter.mode == ColorMode.COLOR_256
