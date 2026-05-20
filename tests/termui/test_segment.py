"""
Module: tests/termui/test_segment.py
Description: Tests for Segment styled text fragment.
Author: Zev
Date: 2026-05-20
"""

from __future__ import annotations

from pigit.termui._segment import Segment
from pigit.termui.palette import (
    STYLE_BOLD,
    STYLE_DIM,
    STYLE_ITALIC,
    STYLE_REVERSE,
)


class TestSegmentFactories:
    def test_bold(self):
        s = Segment.bold("hi", fg=(255, 0, 0))
        assert s.text == "hi"
        assert s.fg == (255, 0, 0)
        assert s.style_flags == STYLE_BOLD

    def test_dim_default_fg(self):
        from pigit.termui.palette import DEFAULT_FG_DIM

        s = Segment.dim("lo")
        assert s.fg == DEFAULT_FG_DIM
        assert s.style_flags == STYLE_DIM

    def test_dim_custom_fg(self):
        s = Segment.dim("lo", fg=(100, 100, 100))
        assert s.fg == (100, 100, 100)

    def test_reverse(self):
        s = Segment.reverse("mid", fg=(1, 2, 3), bg=(4, 5, 6))
        assert s.fg == (1, 2, 3)
        assert s.bg == (4, 5, 6)
        assert s.style_flags == STYLE_REVERSE


class TestSegmentMethods:
    def test_has_style(self):
        s = Segment("x", style_flags=STYLE_BOLD | STYLE_ITALIC)
        assert s.has_style(STYLE_BOLD)
        assert s.has_style(STYLE_ITALIC)
        assert not s.has_style(STYLE_DIM)

    def test_has_style_none(self):
        s = Segment("x")
        assert not s.has_style(STYLE_BOLD)


class TestSegmentRepr:
    def test_normal(self):
        s = Segment("abc")
        assert repr(s) == "Segment('abc', fg=None, bg=None, normal)"

    def test_bold(self):
        s = Segment.bold("abc")
        assert "bold" in repr(s)

    def test_bold_dim(self):
        s = Segment("abc", style_flags=STYLE_BOLD | STYLE_DIM)
        r = repr(s)
        assert "bold" in r
        assert "dim" in r

    def test_reverse(self):
        s = Segment.reverse("abc")
        assert "reverse" in repr(s)


class TestSegmentEq:
    def test_equal(self):
        a = Segment("x", fg=(1, 2, 3), bg=(4, 5, 6), style_flags=STYLE_BOLD)
        b = Segment("x", fg=(1, 2, 3), bg=(4, 5, 6), style_flags=STYLE_BOLD)
        assert a == b

    def test_not_equal_text(self):
        assert Segment("a") != Segment("b")

    def test_not_equal_fg(self):
        assert Segment("x", fg=(1, 2, 3)) != Segment("x", fg=(3, 2, 1))

    def test_not_equal_bg(self):
        assert Segment("x", bg=(1, 2, 3)) != Segment("x", bg=(3, 2, 1))

    def test_not_equal_flags(self):
        assert Segment("x", style_flags=STYLE_BOLD) != Segment(
            "x", style_flags=STYLE_DIM
        )

    def test_not_implemented(self):
        assert Segment("x") != "x"


class TestSegmentHash:
    def test_hashable(self):
        a = Segment("x", fg=(1, 2, 3), style_flags=STYLE_BOLD)
        b = Segment("x", fg=(1, 2, 3), style_flags=STYLE_BOLD)
        assert hash(a) == hash(b)

    def test_different_hash(self):
        assert hash(Segment("a")) != hash(Segment("b"))
