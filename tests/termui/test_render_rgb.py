# -*- coding: utf-8 -*-
"""Tests for RGB rendering in pigit.termui._renderer."""

from __future__ import annotations

from unittest import mock

from pigit.termui._color import ColorMode
from pigit.termui._surface import FlatCell, Surface
from pigit.termui._renderer import Renderer


class FakeSession:
    def __init__(self):
        self.stdout = mock.Mock()


class TestRowToStrRGB:
    def test_plain_cells_use_legacy_path(self):
        """Cells with default RGB should route through legacy renderer."""
        r = Renderer(FakeSession())
        row = [FlatCell("a"), FlatCell("b"), FlatCell("c")]
        assert r._row_to_str(row) == "abc"

    def test_rgb_cells_generate_truecolor_sequences(self):
        r = Renderer(FakeSession())
        row = [
            FlatCell("A", fg=(255, 0, 0)),
            FlatCell("B", fg=(255, 0, 0)),
        ]
        result = r._row_to_str(row)
        assert result == "\033[38;2;255;0;0mAB\033[0m"

    def test_rgb_fg_and_bg(self):
        r = Renderer(FakeSession())
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
        assert result.endswith("\033[0m")

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
        s = Surface(3, 1)
        s.draw_text_rgb(0, 0, "AB", fg=(255, 0, 0))
        r.render_surface(s)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "\033[38;2;255;0;0m" in written
        assert "\033[0m" in written

    def test_256_mode_generates_256_codes(self):
        sess = FakeSession()
        r = Renderer(sess)
        r._color = ColorMode.COLOR_256
        # Need to replace the adapter
        from pigit.termui._color import ColorAdapter

        r._color = ColorAdapter(ColorMode.COLOR_256)
        s = Surface(1, 1)
        s.draw_text_rgb(0, 0, "X", fg=(255, 0, 0))
        r.render_surface(s)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "38;5;" in written or "\033[9m" in written


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
        s.draw_text(1, 0, "def")
        r.render_surface(s)
        sess.stdout.reset_mock()
        s.draw_text(1, 0, "xyz")
        r.render_surface(s)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "abc" not in written
        assert "xyz" in written
