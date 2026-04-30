# -*- coding: utf-8 -*-
"""Tests for pigit.app_chrome components."""

from __future__ import annotations

from pigit.app_chrome import AppFooter
from pigit.app_theme import THEME
from pigit.termui import Header, Segment
from pigit.termui.palette import STYLE_BOLD
from pigit.termui._surface import Surface


class TestHeader:
    def test_render_basic(self):
        h = Header(separator=True, sep_fg=THEME.fg_dim)
        h.set_left(
            [
                Segment("my-repo", fg=THEME.fg_primary),
                Segment("  ", fg=THEME.fg_dim),
                Segment("main", fg=THEME.accent_cyan),
            ]
        )
        h.set_right(
            [
                Segment("Status", fg=THEME.fg_muted, style_flags=STYLE_BOLD),
                Segment(" [1]", fg=THEME.fg_primary, style_flags=STYLE_BOLD),
            ]
        )
        s = Surface(40, 2)
        h.resize((40, 2))
        h._render_surface(s)
        # Row 0: content
        assert "my-repo" in s.lines()[0]
        assert "main" in s.lines()[0]
        # Row 1: separator line
        assert "\u2500" in s.lines()[1]

    def test_render_with_center(self):
        h = Header(separator=True, sep_fg=THEME.fg_dim)
        h.set_left(
            [
                Segment("r", fg=THEME.fg_primary),
                Segment("  ", fg=THEME.fg_dim),
                Segment("b", fg=THEME.accent_cyan),
            ]
        )
        h.set_center(
            [
                Segment("\u21912 ", fg=THEME.accent_green),
                Segment("\u21931", fg=THEME.accent_yellow),
            ]
        )
        s = Surface(30, 2)
        h.resize((30, 2))
        h._render_surface(s)
        line = s.lines()[0]
        assert "\u21912" in line  # ↑2
        assert "\u21931" in line  # ↓1
        assert "\u2500" in s.lines()[1]  # separator

    def test_render_truncates_on_small_width(self):
        h = Header(separator=True, sep_fg=THEME.fg_dim)
        h.set_left(
            [
                Segment("very-long-repo-name", fg=THEME.fg_primary),
                Segment("  ", fg=THEME.fg_dim),
                Segment("feature", fg=THEME.accent_cyan),
            ]
        )
        s = Surface(10, 2)
        h.resize((10, 2))
        h._render_surface(s)
        line = s.lines()[0]
        assert "\u2026" in line or "very" in line
        assert "\u2500" in s.lines()[1]  # separator

    def test_set_slots_updates_fields(self):
        h = Header()
        h.set_left([Segment("repo", fg=THEME.fg_primary)])
        h.set_center([Segment("center", fg=THEME.fg_dim)])
        h.set_right([Segment("right", fg=THEME.fg_muted, style_flags=STYLE_BOLD)])
        assert h._left == [Segment("repo", fg=THEME.fg_primary)]
        assert h._center == [Segment("center", fg=THEME.fg_dim)]
        assert h._right == [Segment("right", fg=THEME.fg_muted, style_flags=STYLE_BOLD)]


class TestAppFooter:
    def test_render_basic(self):
        f = AppFooter(THEME)
        f.set_context("src/app.py")
        f.set_global_help([("Q", "Quit")])
        f.set_help_provider(lambda: [("Enter", "Diff"), ("Space", "Stage")])
        s = Surface(50, 2)
        f.resize((50, 2))
        f._render_surface(s)
        # Row 0: separator line
        assert "\u2500" in s.lines()[0]
        # Row 1: content
        assert "src/app.py" in s.lines()[1]
        assert "Enter" in s.lines()[1]

    def test_render_empty(self):
        f = AppFooter(THEME)
        s = Surface(20, 2)
        f.resize((20, 2))
        f._render_surface(s)
        # Should not crash
        assert "\u2500" in s.lines()[0]

    def test_set_context_clears_text(self):
        f = AppFooter(THEME)
        f.set_context("file")
        assert f._context_text == "\u2192 file"
        f.set_context("")
        assert f._context_text == ""
