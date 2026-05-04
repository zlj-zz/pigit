# -*- coding: utf-8 -*-
"""Tests for pigit.termui.render."""

from __future__ import annotations

from unittest import mock

from pigit.termui._color import ColorAdapter, ColorMode
from pigit.termui._surface import Cell, FlatCell, Surface
from pigit.termui._renderer import Renderer
from pigit.termui.palette import DEFAULT_BG, DEFAULT_FG


class FakeSession:
    def __init__(self):
        self.stdout = mock.Mock()


class TestRowToStr:
    def test_plain_cells(self):
        r = Renderer(FakeSession())
        row = [Cell("a"), Cell("b"), Cell("c")]
        assert r._row_to_str(row) == "abc"

    def test_skips_empty_spacer_cells(self):
        r = Renderer(FakeSession())
        row = [Cell("中"), Cell(""), Cell("a")]
        assert r._row_to_str(row) == "中a"

    def test_style_transitions_and_resets(self):
        r = Renderer(FakeSession())
        row = [
            Cell("a", style="\033[31m"),
            Cell("b", style="\033[31m"),
            Cell("c", style="\033[32m"),
            Cell("d"),
        ]
        result = r._row_to_str(row)
        assert result == "\033[31mab\033[0m\033[32mc\033[0md"

    def test_mixed_empty_and_style_cells(self):
        r = Renderer(FakeSession())
        row = [
            Cell(""),
            Cell("x", style="\033[1m"),
            Cell(""),
            Cell("y"),
        ]
        assert r._row_to_str(row) == "\033[1mx\033[0my"


class TestRenderSurface:
    def test_first_frame_does_full_clear(self):
        sess = FakeSession()
        r = Renderer(sess)
        s = Surface(5, 2)
        s.draw_text_rgb(0, 0, "hello", fg=DEFAULT_FG, bg=DEFAULT_BG)
        s.draw_text_rgb(1, 0, "world", fg=DEFAULT_FG, bg=DEFAULT_BG)
        r.render_surface(s)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "\033[2J" in written

    def test_second_frame_only_rewrites_changed_rows(self):
        sess = FakeSession()
        r = Renderer(sess)
        s = Surface(7, 3)
        s.draw_text_rgb(0, 0, "hello  ", fg=DEFAULT_FG, bg=DEFAULT_BG)
        s.draw_text_rgb(1, 0, "world  ", fg=DEFAULT_FG, bg=DEFAULT_BG)
        s.draw_text_rgb(2, 0, "stay   ", fg=DEFAULT_FG, bg=DEFAULT_BG)
        r.render_surface(s)
        sess.stdout.reset_mock()
        s.draw_text_rgb(1, 0, "changed", fg=DEFAULT_FG, bg=DEFAULT_BG)
        r.render_surface(s)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "\033[2J" not in written
        assert "changed" in written
        assert "hello" not in written
        assert "stay" not in written

    def test_clear_cache_triggers_full_clear_next_frame(self):
        sess = FakeSession()
        r = Renderer(sess)
        s = Surface(3, 1)
        s.draw_text_rgb(0, 0, "abc", fg=DEFAULT_FG, bg=DEFAULT_BG)
        r.render_surface(s)
        sess.stdout.reset_mock()
        r.clear_cache()
        r.render_surface(s)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "\033[2J" in written

    def test_dimension_change_triggers_full_clear(self):
        sess = FakeSession()
        r = Renderer(sess)
        s1 = Surface(3, 1)
        s1.draw_text_rgb(0, 0, "abc", fg=DEFAULT_FG, bg=DEFAULT_BG)
        s2 = Surface(4, 1)
        s2.draw_text_rgb(0, 0, "abcd", fg=DEFAULT_FG, bg=DEFAULT_BG)
        r.render_surface(s1)
        sess.stdout.reset_mock()
        r.render_surface(s2)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "\033[2J" in written

    def test_no_rows_surface_does_not_crash(self):
        sess = FakeSession()
        r = Renderer(sess)
        s = Surface(0, 0)
        r.render_surface(s)
        assert True

    def test_rgb_end_to_end_via_draw_text_rgb(self):
        sess = FakeSession()
        r = Renderer(sess)
        r._color = ColorAdapter(ColorMode.TRUECOLOR)
        s = Surface(3, 1)
        s.draw_text_rgb(0, 0, "AB", fg=(255, 0, 0), bg=DEFAULT_BG)
        r.render_surface(s)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "\033[38;2;255;0;0m" in written
        # Trailing reset is omitted when the last cell returns to default
        assert "\033[39m" in written


class TestRendererUtilities:
    def test_write_and_flush(self):
        sess = FakeSession()
        r = Renderer(sess)
        r.write("hi")
        sess.stdout.write.assert_called_with("hi")
        r.flush()
        sess.stdout.flush.assert_called_once()

    def test_hide_and_show_cursor(self):
        sess = FakeSession()
        r = Renderer(sess)
        r.hide_cursor()
        assert "\033[?25l" in sess.stdout.write.call_args[0][0]
        r.show_cursor()
        assert "\033[?25h" in sess.stdout.write.call_args[0][0]

    def test_draw_absolute_row(self):
        sess = FakeSession()
        r = Renderer(sess)
        r.draw_absolute_row(3, "hello")
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "\033[3;1f" in written
        assert "\033[K" in written
        assert "hello" in written

    def test_draw_block(self):
        sess = FakeSession()
        r = Renderer(sess)
        r.draw_block(["ab", "cd"], 1, 1, 3, 2)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "\033[1;1f" in written
        assert "ab" in written
        assert "cd" in written

    def test_draw_panel(self):
        sess = FakeSession()
        r = Renderer(sess)
        r.draw_panel(["ab", "cd"], 1, 1, size=(5, 3))
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "\033[1;1f" in written
        assert "ab" in written
        assert "     " in written


class TestRowToStrRGB:
    def test_plain_cells_use_legacy_path(self):
        """Cells with default RGB should route through legacy renderer."""
        r = Renderer(FakeSession())
        row = [FlatCell("a"), FlatCell("b"), FlatCell("c")]
        assert r._row_to_str(row) == "abc"

    def test_rgb_cells_generate_truecolor_sequences(self):
        r = Renderer(FakeSession())
        r._color = ColorAdapter(ColorMode.TRUECOLOR)
        row = [
            FlatCell("A", fg=(255, 0, 0)),
            FlatCell("B", fg=(255, 0, 0)),
        ]
        result = r._row_to_str(row)
        assert result == "\033[38;2;255;0;0mAB\033[0m"

    def test_rgb_fg_and_bg(self):
        r = Renderer(FakeSession())
        r._color = ColorAdapter(ColorMode.TRUECOLOR)
        row = [FlatCell("X", fg=(255, 0, 0), bg=(0, 0, 255))]
        result = r._row_to_str(row)
        assert "\033[38;2;255;0;0m" in result
        assert "\033[48;2;0;0;255m" in result
        assert result.endswith("\033[0m")

    def test_rgb_bold(self):
        r = Renderer(FakeSession())
        row = [FlatCell("B", bold=True)]
        result = r._row_to_str(row)
        assert result == "\033[1mB\033[0m"

    def test_rgb_skips_empty_spacer_cells(self):
        r = Renderer(FakeSession())
        row = [FlatCell("中"), FlatCell(""), FlatCell("a", fg=(255, 0, 0))]
        result = r._row_to_str(row)
        assert "中" in result
        assert "a" in result

    def test_rgb_default_colors_no_sequences(self):
        r = Renderer(FakeSession())
        row = [FlatCell("x")]
        result = r._row_to_str(row)
        assert result == "x"

    def test_rgb_transition_back_to_default(self):
        r = Renderer(FakeSession())
        row = [
            FlatCell("R", fg=(255, 0, 0)),
            FlatCell("D"),  # default fg
        ]
        result = r._row_to_str(row)
        assert "\033[39m" in result
        # Trailing reset is omitted when the last cell returns to default
        assert not result.endswith("\033[0m")

    def test_mixed_legacy_and_rgb(self):
        r = Renderer(FakeSession())
        row = [
            FlatCell("x", ansi_style="\033[1m"),
            FlatCell("y"),  # default RGB
        ]
        result = r._row_to_str(row)
        assert result == "\033[1mx\033[0my"

    def test_mixed_rgb_then_legacy(self):
        r = Renderer(FakeSession())
        row = [
            FlatCell("r", fg=(255, 0, 0)),
            FlatCell("b", ansi_style="\033[1m"),
        ]
        result = r._row_to_str(row)
        assert "\033[0m\033[1m" in result


class TestRenderSurfaceRGB:
    def test_rgb_end_to_end(self):
        sess = FakeSession()
        r = Renderer(sess)
        r._color = ColorAdapter(ColorMode.TRUECOLOR)
        s = Surface(3, 1)
        s.draw_text_rgb(0, 0, "AB", fg=(255, 0, 0))
        r.render_surface(s)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "\033[38;2;255;0;0m" in written
        # Trailing reset is omitted when the last cell returns to default
        assert "\033[39m" in written

    def test_256_mode_generates_256_codes(self):
        sess = FakeSession()
        r = Renderer(sess)
        r._color = ColorAdapter(ColorMode.COLOR_256)
        s = Surface(1, 1)
        s.draw_text_rgb(0, 0, "X", fg=(255, 0, 0))
        r.render_surface(s)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "\033[38;5;9m" in written


class TestRenderSurfaceIncrementalWithRGB:
    def test_second_frame_rewrites_changed_rgb_rows(self):
        sess = FakeSession()
        r = Renderer(sess)
        s = Surface(3, 1)
        s.draw_text_rgb(0, 0, "abc", fg=(255, 0, 0))
        r.render_surface(s)
        sess.stdout.reset_mock()
        s.draw_text_rgb(0, 0, "xyz", fg=(255, 0, 0))
        r.render_surface(s)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "\033[2J" not in written
        assert "xyz" in written

    def test_unchanged_rgb_row_not_rewritten(self):
        sess = FakeSession()
        r = Renderer(sess)
        s = Surface(3, 2)
        s.draw_text_rgb(0, 0, "abc", fg=(255, 0, 0))
        s.draw_text_rgb(1, 0, "def", fg=DEFAULT_FG, bg=DEFAULT_BG)
        r.render_surface(s)
        sess.stdout.reset_mock()
        s.draw_text_rgb(1, 0, "xyz", fg=DEFAULT_FG, bg=DEFAULT_BG)
        r.render_surface(s)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "abc" not in written
        assert "xyz" in written
