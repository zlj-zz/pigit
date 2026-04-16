# -*- coding: utf-8 -*-
"""Tests for pigit.termui.render."""

from __future__ import annotations

from unittest import mock

from pigit.termui.surface import Cell, Surface
from pigit.termui.render import Renderer


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
        s.draw_text(0, 0, "hello")
        s.draw_text(1, 0, "world")
        r.render_surface(s)
        written = "".join(c[0][0] for c in sess.stdout.write.call_args_list)
        assert "\033[2J" in written

    def test_second_frame_only_rewrites_changed_rows(self):
        sess = FakeSession()
        r = Renderer(sess)
        s = Surface(7, 3)
        s.draw_text(0, 0, "hello  ")
        s.draw_text(1, 0, "world  ")
        s.draw_text(2, 0, "stay   ")
        r.render_surface(s)
        sess.stdout.reset_mock()
        s.draw_text(1, 0, "changed")
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
        s.draw_text(0, 0, "abc")
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
        s1.draw_text(0, 0, "abc")
        s2 = Surface(4, 1)
        s2.draw_text(0, 0, "abcd")
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
