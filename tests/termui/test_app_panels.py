# -*- coding: utf-8 -*-
"""Tests for pigit app panel components."""

from __future__ import annotations

import pytest

from pigit.app_diff import DiffViewer
from pigit.termui._surface import Surface


class TestDiffViewer:
    def test_init(self):
        d = DiffViewer()
        assert d._content == ""
        assert d._heatmap == []
        assert d._heatmap_colors == []
        assert d._line_numbers == []

    def test_set_content_computes_heatmap(self):
        d = DiffViewer()
        d.set_content(["+added line", "-removed line", "@@ context", " context"])
        assert len(d._heatmap) == 4
        assert len(d._heatmap_colors) == 4
        # Added line gets green symbol
        assert d._heatmap[0] in {"░", "▒", "▓", "█"}
        # Removed line gets red symbol
        assert d._heatmap[1] in {"░", "▒", "▓", "█"}
        # Context lines get space
        assert d._heatmap[2] == " "
        assert d._heatmap[3] == " "

    def test_render_surface_empty(self):
        d = DiffViewer()
        s = Surface(10, 5)
        d._render_surface(s)
        # No crash, no content

    def test_render_surface_diff(self):
        d = DiffViewer()
        d.set_content(["+added", "-removed", " context"])
        d.resize((20, 5))
        s = Surface(20, 5)
        d._render_surface(s)
        # With box border: row 0 = top border, row 1+ = content, last row = bottom border
        lines = s.lines()
        assert "\u250c" in lines[0]  # ┌ top-left corner
        assert "\u2510" in lines[0]  # ┐ top-right corner
        assert "0" in lines[1]
        assert "+added" in lines[1]
        assert "\u2514" in lines[-1]  # └ bottom-left corner
        assert "\u2518" in lines[-1]  # ┘ bottom-right corner

    def test_render_surface_borderless_fallback(self):
        """When surface is too small for borders, fall back to borderless."""
        d = DiffViewer()
        d.set_content(["+added"])
        d.resize((10, 2))
        s = Surface(10, 2)
        d._render_surface(s)
        lines = s.lines()
        # Should render without box border characters
        assert "\u250c" not in lines[0]
        # Borderless renders line number + truncated content + heatmap
        assert "+ad" in lines[0] or "added" in lines[0]

    def test_hunk_navigation(self):
        d = DiffViewer()
        d.set_content(["@@ hunk1", "+line1", "@@ hunk2", "+line2"])
        d._i = 0
        d._next_hunk()
        assert d._i == 2  # jumped to second hunk
        d._prev_hunk()
        assert d._i == 0  # jumped back to first hunk

    def test_scroll_position_cache(self):
        from pigit.termui._component_base import Component
        class FakeSource(Component):
            def _render_surface(self, surface):
                pass
        source = FakeSource()
        d = DiffViewer()
        d._i = 5
        from pigit.termui.types import ActionLiteral
        d.update(ActionLiteral.goto, source=source, key="test.py", content=["line1"])
        assert d.i_cache_key == "test.py"
        assert d.come_from is source

    def test_leave_display_no_parent(self):
        from pigit.termui._component_base import Component
        class FakeSource(Component):
            def _render_surface(self, surface):
                pass
        d = DiffViewer()
        d.come_from = FakeSource()
        # emit requires a parent; should raise AssertionError
        with pytest.raises(AssertionError):
            d._leave_display()

    def test_leave_display_with_parent(self):
        from pigit.termui._component_base import Component
        class FakeParent(Component):
            def __init__(self):
                self._received = []
                super().__init__()
            def _handle_event(self, key):
                pass
            def _render_surface(self, surface):
                pass
            def accept(self, action, **data):
                self._received.append((action, data))
        class FakeSource(Component):
            def _render_surface(self, surface):
                pass
        parent = FakeParent()
        d = DiffViewer()
        d.parent = parent
        source = FakeSource()
        d.come_from = source
        d._leave_display()
        assert len(parent._received) == 1
        assert parent._received[0][0].name == "goto"
        assert parent._received[0][1]["target"] is source

    # -- Wide-character regression tests --

    def test_render_surface_wide_char_no_overflow(self):
        """Regression: CJK diff content must not overflow and overwrite borders."""
        d = DiffViewer()
        d.set_content(["+中文内容测试"])
        d.resize((20, 5))
        s = Surface(20, 5)
        d._render_surface(s)
        lines = s.lines()
        rows = s.rows()
        # Box borders must remain intact
        assert lines[0][0] == "\u250c"  # ┌ top-left
        assert lines[0][-1] == "\u2510"  # ┐ top-right
        assert lines[-1][0] == "\u2514"  # └ bottom-left
        assert lines[-1][-1] == "\u2518"  # ┘ bottom-right
        # Content row must have left/right borders intact
        assert rows[1][0].char == "\u2502"  # │ left border
        assert rows[1][-1].char == "\u2502"  # │ right border

    def test_render_surface_wide_char_heatmap_intact(self):
        """Heatmap symbol must not be overwritten by wide-char diff text."""
        d = DiffViewer()
        d.set_content(["+中文内容测试"])
        d.resize((20, 5))
        s = Surface(20, 5)
        d._render_surface(s)
        # Heatmap is at column w-2 on content rows
        heatmap_col = 18
        for r in range(1, 4):
            cell = s.rows()[r][heatmap_col]
            # Should be a heatmap symbol (not space, not part of diff text)
            assert cell.char in {"\u2591", "\u2592", "\u2593", "\u2588", " "}

    def test_render_surface_borderless_wide_char(self):
        """Borderless fallback must also handle wide chars without overflow."""
        d = DiffViewer()
        d.set_content(["+中文内容测试"])
        # w=8 triggers borderless fallback (w <= LINE_NO_WIDTH + 3 = 8)
        d.resize((8, 3))
        s = Surface(8, 3)
        d._render_surface(s)
        lines = s.lines()
        # Should not have box borders (too small)
        assert "\u250c" not in lines[0]
        # Each row must have exactly surface.width cells
        for row in s.rows():
            assert len(row) == 8
        # Rightmost column should be heatmap symbol (not overwritten)
        cell = s.rows()[0][-1]
        assert cell.char in {"\u2591", "\u2592", "\u2593", "\u2588", " "}

    def test_render_surface_multiple_wide_chars(self):
        """Multiple CJK chars in a row should all render within bounds."""
        d = DiffViewer()
        d.set_content(["+中文内容测试", "-更多中文测试"])
        d.resize((25, 6))
        s = Surface(25, 6)
        d._render_surface(s)
        lines = s.lines()
        rows = s.rows()
        # Every row must have exactly surface.width cells
        for row in rows:
            assert len(row) == 25
        # Borders intact
        assert rows[0][0].char == "\u250c"
        assert rows[0][-1].char == "\u2510"
        assert rows[-1][0].char == "\u2514"
        assert rows[-1][-1].char == "\u2518"

    def test_set_content_expands_tabs(self):
        """Tab characters must be expanded to spaces to prevent width mismatch."""
        d = DiffViewer()
        d.set_content(["+\t\tName"])
        # After expandtabs(8): '+' at col 0, first tab -> 7 spaces to col 8,
        # second tab -> 8 spaces to col 16, then "Name"
        assert "\t" not in d._content[0]
        assert d._content[0] == "+               Name"

    def test_render_surface_with_tabs_no_overflow(self):
        """Regression: tab-heavy diff lines must not overflow surface bounds."""
        d = DiffViewer()
        d.set_content(["+\t\tPotentialRange string"])
        d.resize((40, 5))
        s = Surface(40, 5)
        d._render_surface(s)
        lines = s.lines()
        # Top and bottom borders must be intact
        assert lines[0][0] == "\u250c"
        assert lines[0][-1] == "\u2510"
        assert lines[-1][0] == "\u2514"
        assert lines[-1][-1] == "\u2518"
        # No tab characters should remain in rendered output
        assert "\t" not in lines[1]
        # Right border on content row must be │
        assert s.rows()[1][-1].char == "\u2502"

    def test_update_expands_tabs(self):
        """update() with list content must also expand tabs via set_content."""
        from pigit.termui._component_base import Component
        from pigit.termui.types import ActionLiteral

        class FakeSource(Component):
            def _render_surface(self, surface):
                pass

        d = DiffViewer()
        d.parent = FakeSource()
        d.update(
            ActionLiteral.goto,
            source=FakeSource(),
            key="test.go",
            content=["+\t\tName"],
        )
        assert "\t" not in d._content[0]
        assert d._content[0] == "+               Name"

    def test_render_surface_blank_rows_have_borders(self):
        """When content is shorter than viewport, blank rows must keep borders."""
        d = DiffViewer()
        d.set_content(["+line1", "-line2"])
        d.resize((20, 8))
        s = Surface(20, 8)
        d._render_surface(s)
        rows = s.rows()
        # Row 0: top border
        assert rows[0][0].char == "\u250c"
        # Row 1-2: content rows with borders
        assert rows[1][0].char == "\u2502"
        assert rows[1][-1].char == "\u2502"
        assert rows[2][0].char == "\u2502"
        assert rows[2][-1].char == "\u2502"
        # Row 3-6: blank rows must still have left/right borders
        for r in range(3, 7):
            assert rows[r][0].char == "\u2502", f"row {r} missing left border"
            assert rows[r][-1].char == "\u2502", f"row {r} missing right border"
        # Row 7: bottom border
        assert rows[7][0].char == "\u2514"
