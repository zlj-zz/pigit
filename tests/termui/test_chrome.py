# -*- coding: utf-8 -*-
"""Tests for pigit.app_chrome components."""

from __future__ import annotations

from pigit.app_chrome import AppFooter
from pigit.app_theme import THEME
from pigit.termui import Header
from pigit.termui._surface import Surface


class TestHeader:
    def test_render_basic(self):
        h = Header(separator=True, sep_fg=THEME.fg_dim)
        h.set_left(
            [
                ("my-repo", THEME.fg_primary, False),
                ("  ", THEME.fg_dim, False),
                ("main", THEME.accent_cyan, False),
            ]
        )
        h.set_right(
            [
                ("Status", THEME.fg_muted, True),
                (" [1]", THEME.fg_primary, True),
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
                ("r", THEME.fg_primary, False),
                ("  ", THEME.fg_dim, False),
                ("b", THEME.accent_cyan, False),
            ]
        )
        h.set_center(
            [
                ("\u21912 ", THEME.accent_green, False),
                ("\u21931", THEME.accent_yellow, False),
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
                ("very-long-repo-name", THEME.fg_primary, False),
                ("  ", THEME.fg_dim, False),
                ("feature", THEME.accent_cyan, False),
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
        h.set_left([("repo", THEME.fg_primary, False)])
        h.set_center([("center", THEME.fg_dim, False)])
        h.set_right([("right", THEME.fg_muted, True)])
        assert h._left == [("repo", THEME.fg_primary, False)]
        assert h._center == [("center", THEME.fg_dim, False)]
        assert h._right == [("right", THEME.fg_muted, True)]


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
