# -*- coding: utf-8 -*-
"""Tests for pigit.app_footer components."""

from __future__ import annotations

from pigit.app_footer import AppFooter
from pigit.app_theme import THEME
from pigit.termui import Component, ComponentRoot, Segment
from pigit.termui.types import LayerKind
from pigit.termui.widgets import Footer, Header, Sheet
from pigit.termui.widgets import Popup
from pigit.termui.widgets.binding_browser import BindingBrowser
from pigit.termui.palette import STYLE_BOLD
from pigit.termui.surface import Surface
from pigit.termui.theme import get_theme


class TestHeader:
    def test_render_basic(self):
        h = Header(separator=True, sep_fg=THEME.fg_dim)
        h.left = [
            Segment("my-repo", fg=THEME.fg_primary),
            Segment("  ", fg=THEME.fg_dim),
            Segment("main", fg=THEME.fg_branch_name),
        ]
        h.right = [
            Segment("Status", fg=THEME.fg_muted, style_flags=STYLE_BOLD),
            Segment(" [1]", fg=THEME.fg_primary, style_flags=STYLE_BOLD),
        ]
        s = Surface(40, 2)
        h.resize((40, 2))
        h.paint(s)
        # Row 0: content
        assert "my-repo" in s.lines()[0]
        assert "main" in s.lines()[0]
        # Row 1: separator line
        assert "─" in s.lines()[1]

    def test_render_with_center(self):
        h = Header(separator=True, sep_fg=THEME.fg_dim)
        h.left = [
            Segment("r", fg=THEME.fg_primary),
            Segment("  ", fg=THEME.fg_dim),
            Segment("b", fg=THEME.fg_branch_name),
        ]
        h.center = [
            Segment("↑2 ", fg=THEME.fg_success),
            Segment("↓1", fg=THEME.fg_warning),
        ]
        s = Surface(30, 2)
        h.resize((30, 2))
        h.paint(s)
        line = s.lines()[0]
        assert "↑2" in line  # up arrow 2
        assert "↓1" in line  # down arrow 1
        assert "─" in s.lines()[1]  # separator

    def test_render_truncates_on_small_width(self):
        h = Header(separator=True, sep_fg=THEME.fg_dim)
        h.left = [
            Segment("very-long-repo-name", fg=THEME.fg_primary),
            Segment("  ", fg=THEME.fg_dim),
            Segment("feature", fg=THEME.fg_branch_name),
        ]
        s = Surface(10, 2)
        h.resize((10, 2))
        h.paint(s)
        line = s.lines()[0]
        assert "…" in line or "very" in line
        assert "─" in s.lines()[1]  # separator

    def test_set_slots_updates_fields(self):
        h = Header()
        h.left = [Segment("repo", fg=THEME.fg_primary)]
        h.center = [Segment("center", fg=THEME.fg_dim)]
        h.right = [Segment("right", fg=THEME.fg_muted, style_flags=STYLE_BOLD)]
        assert h.left == [Segment("repo", fg=THEME.fg_primary)]
        assert h.center == [Segment("center", fg=THEME.fg_dim)]
        assert h.right == [Segment("right", fg=THEME.fg_muted, style_flags=STYLE_BOLD)]


class TestFooter:
    def test_render_context_and_help(self):
        theme = get_theme()
        f = Footer()
        f.set_context("src/main.py")
        f.set_global_help([("Q", "Quit")])
        f.set_help_provider(lambda: [("Enter", "Open")])
        s = Surface(50, 2)
        f.resize((50, 2))
        f.paint(s)
        assert "─" in s.lines()[0]
        content = s.lines()[1]
        assert "main.py" in content
        assert "Enter" in content
        row_cells = s.rows()[1]
        key_cell = next(c for c in row_cells if c.char == "E")
        assert key_cell.fg == theme.fg_accent
        assert key_cell.style_flags & STYLE_BOLD


class TestAppFooter:
    def test_render_basic(self):
        f = AppFooter(THEME)
        f.set_context("src/app.py")
        f.set_global_help([("Q", "Quit")])
        f.set_help_provider(lambda: [("Enter", "Diff"), ("Space", "Stage")])
        s = Surface(50, 2)
        f.resize((50, 2))
        f.paint(s)
        # Row 0: separator line
        assert "─" in s.lines()[0]
        # Row 1: content
        assert "src/app.py" in s.lines()[1]
        assert "Enter" in s.lines()[1]

    def test_render_empty(self):
        f = AppFooter(THEME)
        s = Surface(20, 2)
        f.resize((20, 2))
        f.paint(s)
        # Should not crash
        assert "─" in s.lines()[0]

    def test_set_context_clears_text(self):
        f = AppFooter(THEME)
        f.set_context("file")
        assert f._context_text == "→ file"
        f.set_context("")
        assert f._context_text == ""

    def test_modal_footer_omits_global_and_context(self):
        from pigit.termui.component import collect_overlay_footer_entries
        from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx

        browser = BindingBrowser()
        popup = Popup(browser, exit_key="esc")
        popup.show()
        pairs = collect_overlay_footer_entries(popup)
        tips = {tip for _key, tip in pairs}
        assert "Navigate" in tips
        assert "Run" in tips
        assert "Close" in tips

        ctx = RuntimeContext()
        token = _runtime_ctx.set(ctx)
        try:
            body = Component(id="body")
            root = ComponentRoot(body, ctx.registry)
            ctx.overlay_host = root
            root._layer_stack.push(LayerKind.MODAL, popup)
            f = AppFooter(THEME)
            f.set_context("src/main.py")
            f.set_global_help([("Q", "Quit"), (";", "Palette")])
            f.set_help_provider(lambda: [("Enter", "Open")])
            s = Surface(80, 2)
            f.resize((80, 2))
            f.paint(s)
            content = s.lines()[1]
            assert "Navigate" in content
            assert "Quit" not in content
            assert "Palette" not in content
            assert "main.py" not in content
        finally:
            _runtime_ctx.reset(token)

    def test_sheet_footer_omits_global_and_context(self):
        from pigit.app_welcome import WelcomeSheet
        from pigit.termui import Segment
        from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx

        rows = [[Segment(f"line {i}")] for i in range(30)]
        welcome = WelcomeSheet(on_dismiss=lambda: None, rows=rows)
        sheet_shell = Sheet(
            welcome, height=8, edge="top", title_core=" · Welcome to Pigit · "
        )
        tips = {tip for _key, tip in welcome.get_footer_entries()}
        assert "Navigate" in tips
        assert "Close" in tips

        ctx = RuntimeContext()
        token = _runtime_ctx.set(ctx)
        try:
            body = Component(id="body")
            root = ComponentRoot(body, ctx.registry)
            ctx.overlay_host = root
            root._layer_stack.push(LayerKind.SHEET, sheet_shell)
            f = AppFooter(THEME)
            f.set_context("src/main.py")
            f.set_global_help([("Q", "Quit"), (";", "Palette")])
            f.set_help_provider(lambda: [("Enter", "Open")])
            s = Surface(80, 2)
            f.resize((80, 2))
            f.paint(s)
            content = s.lines()[1]
            assert "Navigate" in content
            assert "Quit" not in content
            assert "Palette" not in content
            assert "main.py" not in content
        finally:
            _runtime_ctx.reset(token)

    def test_sheet_footer_shows_child_hints(self):
        """Overlay branch surfaces sheet key hints once geometry leaves footer free."""
        from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx

        class _HintChild(Component):
            def get_footer_entries(self) -> list[tuple[str, str]]:
                return [("s", "Start")]

            def paint(self, surface) -> None:
                pass

        child = _HintChild()
        sheet_shell = Sheet(child, height=4, edge="bottom")
        ctx = RuntimeContext()
        token = _runtime_ctx.set(ctx)
        try:
            body = Component(id="body")
            root = ComponentRoot(body, ctx.registry)
            ctx.overlay_host = root
            root._layer_stack.push(LayerKind.SHEET, sheet_shell)
            f = AppFooter(THEME)
            f.set_context("src/main.py")
            f.set_global_help([("Q", "Quit"), (";", "Palette")])
            f.set_help_provider(lambda: [("Enter", "Open")])
            assert ("s", "Start") in f._help_pairs()
            s = Surface(80, 2)
            f.resize((80, 2))
            f.paint(s)
            content = s.lines()[1]
            assert "Start" in content
            assert "Quit" not in content
            assert "Palette" not in content
            assert "main.py" not in content
        finally:
            _runtime_ctx.reset(token)

    def test_sheet_bottom_pad_keeps_footer_free(self):
        """Chrome pad end-to-end: sheet stays above the footer and hints stay visible."""
        from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx

        class _HintChild(Component):
            def get_footer_entries(self) -> list[tuple[str, str]]:
                return [("b", "Bad")]

            def paint(self, surface) -> None:
                pass

        ctx = RuntimeContext()
        token = _runtime_ctx.set(ctx)
        try:
            body = Component(id="body")
            root = ComponentRoot(body, ctx.registry)
            ctx.overlay_host = root
            root.top_chrome_pad = 2
            root.bottom_chrome_pad = 2
            root.resize((100, 30))
            sheet = root.show_sheet(_HintChild(), height=4, edge="bottom")
            bottom_row = sheet._origin_row(30, sheet._size[1]) + sheet._size[1]
            assert bottom_row <= 30 - root.bottom_chrome_pad
            f = AppFooter(THEME)
            f.set_global_help([("Q", "Quit")])
            assert ("b", "Bad") in f._help_pairs()
        finally:
            _runtime_ctx.reset(token)
