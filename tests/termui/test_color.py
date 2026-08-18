# -*- coding: utf-8 -*-
"""Tests for pigit.termui._color."""

from __future__ import annotations

import os
from unittest import mock

import pytest

from pigit.termui._color import (
    ColorAdapter,
    ColorMode,
    _ANSI_16_PALETTE,
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
        seq = adapter.fg_sequence((12, 34, 56))
        assert seq == "\033[38;2;12;34;56m"

    def test_truecolor_bg_sequence(self):
        adapter = ColorAdapter(ColorMode.TRUECOLOR)
        seq = adapter.bg_sequence((12, 34, 56))
        assert seq == "\033[48;2;12;34;56m"

    def test_truecolor_ansi16_slots_use_indexed_sgr(self):
        adapter = ColorAdapter(ColorMode.TRUECOLOR)
        assert adapter.fg_sequence(_ANSI_16_PALETTE[1]) == "\033[31m"
        assert adapter.fg_sequence(_ANSI_16_PALETTE[3]) == "\033[33m"
        assert adapter.fg_sequence(_ANSI_16_PALETTE[2]) == "\033[32m"
        assert adapter.fg_sequence(_ANSI_16_PALETTE[6]) == "\033[36m"
        assert adapter.fg_sequence(_ANSI_16_PALETTE[9]) == "\033[91m"
        assert adapter.bg_sequence(_ANSI_16_PALETTE[1]) == "\033[41m"

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
        seq = adapter.fg_sequence((100, 150, 200))
        assert seq.startswith("\033[38;5;")
        assert seq.endswith("m")
        assert "38;2" not in seq

    def test_256_mode_ansi16_slot_uses_indexed_sgr(self):
        adapter = ColorAdapter(ColorMode.COLOR_256)
        assert adapter.fg_sequence((255, 0, 0)) == "\033[91m"

    def test_256_mode_bg_sequence(self):
        adapter = ColorAdapter(ColorMode.COLOR_256)
        seq = adapter.bg_sequence((100, 150, 200))
        assert seq.startswith("\033[48;5;")

    def test_16_mode_returns_bright_red_code(self):
        adapter = ColorAdapter(ColorMode.COLOR_16)
        seq = adapter.fg_sequence((255, 0, 0))
        assert seq == "\033[91m"

    def test_16_mode_bg_sequence(self):
        adapter = ColorAdapter(ColorMode.COLOR_16)
        seq = adapter.bg_sequence((0, 0, 255))
        assert seq == "\033[104m"

    def test_16_mode_bg_bright(self):
        adapter = ColorAdapter(ColorMode.COLOR_16)
        seq = adapter.bg_sequence((128, 128, 128))
        assert seq == "\033[100m"

    def test_style_sequence_reverse(self):
        from pigit.termui.palette import STYLE_REVERSE

        adapter = ColorAdapter(ColorMode.TRUECOLOR)
        assert adapter.style_sequence(STYLE_REVERSE) == "\033[7m"


class TestNearest256:
    @pytest.mark.parametrize(
        "rgb, expected",
        [
            ((0, 0, 0), 0),
            ((255, 255, 255), 15),
            ((255, 0, 0), 9),
            ((128, 128, 128), 8),
        ],
    )
    def test_lookup(self, rgb, expected):
        assert _nearest_256(rgb) == expected

    def test_caching(self):
        result1 = _nearest_256((100, 150, 200))
        result2 = _nearest_256((100, 150, 200))
        assert result1 == result2


class TestNearest16:
    @pytest.mark.parametrize(
        "rgb, expected",
        [
            ((0, 0, 0), 0),
            ((255, 0, 0), 9),
            ((255, 255, 255), 15),
        ],
    )
    def test_lookup(self, rgb, expected):
        assert _nearest_16(rgb) == expected


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

    def test_invalid_env_falls_back(self):
        with mock.patch.dict(
            os.environ,
            {
                "PIGIT_COLOR_MODE": "invalid",
                "TERM": "xterm-256color",
                "COLORTERM": "",
            },
            clear=True,
        ):
            adapter = ColorAdapter()
            assert adapter.mode == ColorMode.COLOR_256

    @pytest.mark.parametrize("term", ["xterm", "screen", "vt100"])
    def test_16_from_simple_term(self, term):
        with mock.patch.dict(
            os.environ,
            {"TERM": term, "COLORTERM": "", "PIGIT_COLOR_MODE": ""},
        ):
            adapter = ColorAdapter()
            assert adapter.mode == ColorMode.COLOR_16

    def test_default_fallback_to_256(self):
        with mock.patch.dict(
            os.environ,
            {"TERM": "unknown", "COLORTERM": "", "PIGIT_COLOR_MODE": ""},
        ):
            adapter = ColorAdapter()
            assert adapter.mode == ColorMode.COLOR_256
