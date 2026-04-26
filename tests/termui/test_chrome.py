# -*- coding: utf-8 -*-
"""Tests for pigit.app_chrome components."""

from __future__ import annotations

from pigit.app_chrome import AppFooter, AppHeader, PeekLabel
from pigit.app_theme import THEME
from pigit.termui._surface import Surface


class TestAppHeader:
    def test_render_basic(self):
        h = AppHeader(THEME, repo_name="my-repo", branch_name="main")
        s = Surface(40, 2)
        h.resize((40, 2))
        h._render_surface(s)
        # Row 0: content
        assert "my-repo" in s.lines()[0]
        assert "main" in s.lines()[0]
        # Row 1: separator line
        assert "\u2500" in s.lines()[1]

    def test_render_with_ahead_behind(self):
        h = AppHeader(THEME, repo_name="r", branch_name="b", ahead=2, behind=1)
        s = Surface(30, 2)
        h.resize((30, 2))
        h._render_surface(s)
        line = s.lines()[0]
        assert "\u21912" in line  # ↑2
        assert "\u21931" in line  # ↓1
        assert "\u2500" in s.lines()[1]  # separator

    def test_render_truncates_on_small_width(self):
        h = AppHeader(THEME, repo_name="very-long-repo-name", branch_name="feature")
        s = Surface(10, 2)
        h.resize((10, 2))
        h._render_surface(s)
        line = s.lines()[0]
        assert "\u2026" in line or "very" in line
        assert "\u2500" in s.lines()[1]  # separator

    def test_set_state_updates_fields(self):
        h = AppHeader(THEME)
        h.set_state(repo_name="repo", branch_name="dev", ahead=5)
        assert h._repo_name == "repo"
        assert h._branch_name == "dev"
        assert h._ahead == 5


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


class TestPeekLabel:
    def test_show_and_visibility(self):
        p = PeekLabel()
        assert not p.is_visible()
        p.show("Status", duration=5.0)
        assert p.is_visible()

    def test_peek_expires(self):
        p = PeekLabel()
        p.show("Status", duration=0.001)
        import time

        time.sleep(0.01)
        assert not p.is_visible()

    def test_render_creates_centered_box(self):
        p = PeekLabel()
        p.show("Test", duration=5.0)
        s = Surface(20, 10)
        p.render(s, THEME)
        # Should draw something in the center
        found = False
        for row in s.rows():
            for cell in row:
                if cell.char == "T":
                    found = True
                    break
        assert found

    def test_render_skips_if_not_visible(self):
        p = PeekLabel()
        s = Surface(10, 5)
        p.render(s, THEME)
        # No change expected
        assert all(c.bg == (18, 18, 22) for row in s.rows() for c in row)

    def test_render_skips_if_too_small(self):
        p = PeekLabel()
        p.show("X", duration=5.0)
        s = Surface(5, 2)
        p.render(s, THEME)
        # Too small to render
