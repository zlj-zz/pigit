# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_ansi.py
Description: Tests for ANSI SGR parsing into Segments.
Author: Zev
Date: 2026-08-18
"""

from __future__ import annotations

from pigit.termui import palette
from pigit.termui._ansi import parse_ansi_line
from pigit.termui._color import _ANSI_16_PALETTE


def test_plain_text_is_one_unstyled_segment() -> None:
    segs = parse_ansi_line("hello")
    assert len(segs) == 1
    assert segs[0].text == "hello"
    assert segs[0].fg is None
    assert segs[0].style_flags == 0


def test_sgr_16_foreground_and_reset() -> None:
    segs = parse_ansi_line("\x1b[32mgreen\x1b[mplain")
    assert [(s.text, s.fg) for s in segs] == [
        ("green", _ANSI_16_PALETTE[2]),
        ("plain", None),
    ]


def test_sgr_bold() -> None:
    segs = parse_ansi_line("\x1b[1mB\x1b[0m")
    assert segs[0].text == "B"
    assert segs[0].style_flags & palette.STYLE_BOLD


def test_sgr_256_foreground() -> None:
    segs = parse_ansi_line("\x1b[38;5;13mX\x1b[0m")
    assert segs[0].text == "X"
    assert segs[0].fg == _ANSI_16_PALETTE[13]


def test_sgr_truecolor_foreground() -> None:
    segs = parse_ansi_line("\x1b[38;2;10;20;30mX\x1b[0m")
    assert segs[0].fg == (10, 20, 30)


def test_osc_8_hyperlink_is_stripped() -> None:
    segs = parse_ansi_line("\x1b]8;;http://example.com\x1b\\abc")
    assert segs[0].text == "abc"
    assert "\x1b" not in segs[0].text
