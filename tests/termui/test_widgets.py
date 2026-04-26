# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_widgets.py
Description: Unit tests for StatusBar, InputLine, and ItemSelector widgets.
Author: Zev
Date: 2026-04-20
"""

from pigit.termui._component_widgets import (
    InputLine,
    ItemSelector,
    StatusBar,
)
from pigit.termui._reactive import Signal


class TestItemSelector:
    def test_viewport_start(self):
        sel = ItemSelector(content=["a", "b", "c"])
        assert sel.viewport_start == 0

    def test_visible_row_count(self):
        sel = ItemSelector(content=["a", "b", "c"], size=(10, 5))
        assert sel.visible_row_count == 5


class TestStatusBar:
    def test_init_with_string(self):
        bar = StatusBar(text="hello")
        assert bar._text == "hello"

    def test_init_with_signal(self):
        sig = Signal("init")
        bar = StatusBar(text=sig)
        assert bar._text == "init"
        sig.set("changed")
        assert bar._text == "changed"

    def test_set_text(self):
        bar = StatusBar()
        bar.set_text("ok")
        assert bar._text == "ok"

    def test_destroy_unsubscribes(self):
        sig = Signal("x")
        bar = StatusBar(text=sig)
        bar.destroy()
        sig.set("y")
        assert bar._text == "x"  # should not have updated after destroy


class TestInputLine:
    def test_insert(self):
        inp = InputLine()
        inp.insert("a")
        assert inp.value == "a"
        assert inp._cursor == 1

    def test_backspace(self):
        inp = InputLine()
        inp.insert("a")
        inp.insert("b")
        inp.backspace()
        assert inp.value == "a"
        assert inp._cursor == 1

    def test_delete(self):
        inp = InputLine()
        inp.set_value("ab")
        inp.cursor_left()
        inp.delete()
        assert inp.value == "a"

    def test_max_length(self):
        inp = InputLine(max_length=3)
        inp.insert("a")
        inp.insert("b")
        inp.insert("c")
        inp.insert("d")
        assert inp.value == "abc"

    def test_callback(self):
        called = []
        inp = InputLine(on_value_changed=lambda v: called.append(v))
        inp.insert("x")
        assert called == ["x"]

    def test_clear(self):
        inp = InputLine()
        inp.set_value("abc")
        inp.clear()
        assert inp.value == ""
        assert inp._cursor == 0

    def test_on_submit(self):
        called = []
        inp = InputLine(on_submit=lambda v: called.append(v))
        inp.insert("x")
        inp.on_key("enter")
        assert called == ["x"]

    def test_on_cancel(self):
        called = []
        inp = InputLine(on_cancel=lambda: called.append("cancel"))
        inp.on_key("esc")
        assert called == ["cancel"]

    def test_set_prompt(self):
        inp = InputLine(prompt="/")
        assert inp._prompt == "/"
        inp.set_prompt("git ")
        assert inp._prompt == "git "

    def test_tab_triggers_completion(self):
        inp = InputLine(candidate_provider=lambda text: ["foo", "bar", "baz"])
        inp.insert("f")
        inp.on_key("tab")
        assert inp._showing_candidates is True
        assert inp._candidates == ["foo", "bar", "baz"]
        assert inp.value == "foo"

    def test_tab_with_no_provider_is_ignored(self):
        inp = InputLine()
        inp.insert("x")
        inp.on_key("tab")
        assert inp.value == "x"
        assert not inp._showing_candidates

    def test_completion_navigate_up_down(self):
        inp = InputLine(candidate_provider=lambda text: ["a", "b", "c"])
        inp.on_key("tab")
        assert inp.value == "a"
        inp.on_key("down")
        assert inp.value == "b"
        inp.on_key("down")
        assert inp.value == "c"
        inp.on_key("up")
        assert inp.value == "b"

    def test_completion_enter_closes_without_submit(self):
        submitted = []
        inp = InputLine(
            candidate_provider=lambda text: ["alpha"],
            on_submit=lambda v: submitted.append(v),
        )
        inp.insert("a")
        inp.on_key("tab")
        assert inp._showing_candidates
        inp.on_key("enter")
        assert not inp._showing_candidates
        assert inp.value == "alpha"
        assert submitted == []
        # Second Enter triggers submit
        inp.on_key("enter")
        assert submitted == ["alpha"]

    def test_completion_esc_restores_original(self):
        inp = InputLine(
            candidate_provider=lambda text: ["alpha"],
        )
        inp.set_value("orig")
        inp.on_key("tab")
        assert inp.value == "alpha"
        inp.on_key("esc")
        assert not inp._showing_candidates
        assert inp.value == "orig"

    def test_tab_next_candidate(self):
        inp = InputLine(
            candidate_provider=lambda text: ["a", "b", "c"],
        )
        inp.on_key("tab")
        assert inp.value == "a"
        inp.on_key("tab")
        assert inp.value == "b"
        inp.on_key("tab")
        assert inp.value == "c"
        # does not wrap past end
        inp.on_key("tab")
        assert inp.value == "c"

    def test_shift_tab_prev_candidate(self):
        inp = InputLine(
            candidate_provider=lambda text: ["a", "b", "c"],
        )
        inp.on_key("tab")
        inp.on_key("tab")
        inp.on_key("tab")
        assert inp.value == "c"
        inp.on_key("shift tab")
        assert inp.value == "b"
        inp.on_key("shift tab")
        assert inp.value == "a"
        # does not wrap past start
        inp.on_key("shift tab")
        assert inp.value == "a"

    def test_set_candidate_provider_none_disables_tab(self):
        inp = InputLine(
            candidate_provider=lambda text: ["x"],
        )
        inp.on_key("tab")
        assert inp._showing_candidates
        inp.set_candidate_provider(None)
        inp.on_key("tab")
        assert not inp._showing_candidates

    def test_render_with_candidates(self):
        from pigit.termui._surface import Surface

        inp = InputLine(
            prompt="> ",
            candidate_provider=lambda text: ["abc"],
            size=(20, 1),
        )
        inp.set_value("a")
        inp.on_key("tab")
        s = Surface(20, 1)
        inp._render_surface(s)
        assert s.lines()[0].startswith("> abc")
        row_cells = s.rows()[0]
        # Matched part "> a" stays normal
        assert row_cells[0].style == ""
        assert row_cells[2].style == ""
        # Suffix "bc" is dim
        assert row_cells[3].style == "\033[2m"
        assert row_cells[4].style == "\033[2m"

    def test_render_draws_block_cursor(self, mocker):
        mock_surface = mocker.Mock()
        mock_surface.width = 10
        inp = InputLine(prompt="> ", size=(10, 1))
        inp.set_value("hi")
        inp._render_surface(mock_surface)
        # Text is drawn via draw_row, then block cursor is drawn via draw_text
        # at cursor position (prompt_len + cursor = 2 + 2 = 4) as reverse video.
        mock_surface.draw_row.assert_called_once()
        mock_surface.draw_text.assert_called_once_with(0, 4, "\033[7m \033[0m")

    def test_render_block_cursor_in_candidate_mode(self, mocker):
        mock_surface = mocker.Mock()
        mock_surface.width = 12
        inp = InputLine(
            candidate_provider=lambda text: ["opt"],
            size=(12, 1),
        )
        inp.set_value("o")
        inp.on_key("tab")
        inp._render_surface(mock_surface)
        # Candidate mode draws prefix + dim suffix, then block cursor at end.
        calls = mock_surface.draw_text.call_args_list
        # Last call should be the block cursor at position 3 ("o" + "pt").
        assert calls[-1] == ((0, 3, "\033[7m \033[0m"),) or calls[-1].args == (
            0,
            3,
            "\033[7m \033[0m",
        )

    def test_on_key_plain_text_editing(self):
        inp = InputLine()
        inp.on_key("h")
        inp.on_key("i")
        assert inp.value == "hi"
        inp.on_key("backspace")
        assert inp.value == "h"
        inp.on_key("left")
        assert inp._cursor == 0
        inp.on_key("delete")
        assert inp.value == ""
