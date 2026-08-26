# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_widgets.py
Description: Unit tests for StatusBar, InputLine, and OptionList widgets.
Author: Zev
Date: 2026-04-20
"""

from pigit.termui import keys
from pigit.termui.widgets import (
    CheckList,
    InputLine,
    OptionList,
    StatusBar,
)
from pigit.termui.reactive import Signal


from pigit.termui.segment import Segment
from pigit.termui.surface import Surface
from pigit.termui.theme import get_theme


class TestOptionList:
    def test_viewport_start(self):
        sel = OptionList(content=["a", "b", "c"])
        assert sel.viewport_start == 0

    def test_visible_row_count(self):
        sel = OptionList(content=["a", "b", "c"], size=(10, 5))
        assert sel.visible_row_count == 5

    def test_empty_state_renders_when_content_empty(self):
        sel = OptionList(size=(40, 10), empty_state=[Segment("hello")])
        sel.set_content([])
        surface = Surface(40, 10)
        sel.paint(surface)
        # "hello" should be centered on the surface
        found = False
        for row in surface._rows:
            text = "".join(c.char for c in row).strip()
            if "hello" in text:
                found = True
                break
        assert found

    def test_empty_state_not_rendered_when_content_present(self):
        sel = OptionList(size=(40, 10), empty_state=[Segment("empty")])
        sel.set_content(["real"])
        surface = Surface(40, 10)
        sel.paint(surface)
        # "real" should be rendered, "empty" should not
        all_text = ""
        for row in surface._rows:
            all_text += "".join(c.char for c in row)
        assert "real" in all_text
        assert "empty" not in all_text

    def test_no_empty_state_renders_nothing(self):
        sel = OptionList(size=(40, 10))
        sel.set_content([])
        surface = Surface(40, 10)
        sel.paint(surface)
        # All rows should be empty
        for row in surface._rows:
            assert all(c.char == " " for c in row)


class TestOptionListSearch:
    def test_idle_slash_not_consumed(self):
        """``/`` is a panel bind_action; search_handle_key must not swallow it."""
        sel = OptionList(content=["a", "b"])
        assert sel.search_handle_key("/") is False
        assert sel.search_active is False

    def test_enter_search_and_typing(self):
        changes = []
        sel = OptionList(
            content=["alpha", "beta"], on_search_changed=lambda: changes.append(True)
        )
        sel.enter_search()
        assert sel.search_active is True
        assert sel.search_query == ""
        assert changes == [True]
        assert sel.search_handle_key("a") is True
        assert sel.search_handle_key("l") is True
        assert sel.search_query == "al"
        assert sel.search_handle_key(keys.KEY_BACKSPACE) is True
        assert sel.search_query == "a"

    def test_esc_exits_and_clears_query(self):
        sel = OptionList(content=["a"])
        sel.enter_search()
        sel.search_handle_key("x")
        assert sel.search_handle_key(keys.KEY_ESC) is True
        assert sel.search_active is False
        assert sel.search_query == ""

    def test_enter_deactivates_but_keeps_query(self):
        sel = OptionList(content=["a"])
        sel.enter_search()
        sel.search_handle_key("a")
        sel.search_handle_key("b")
        assert sel.search_handle_key(keys.KEY_ENTER) is True
        assert sel.search_active is False
        assert sel.search_query == "ab"

    def test_set_source_items_and_filter_mapping(self):
        items = ["alpha", "beta", "other"]
        sel = OptionList(size=(20, 5))
        sel.set_source_items(items, text_of=lambda x: x)
        sel.set_filter("a")
        assert sel.content == ["alpha", "beta"]
        assert sel.visible_to_source(0) == 0
        assert sel.visible_to_source(1) == 1
        sel.set_filter("al")
        assert sel.content == ["alpha"]
        assert sel.visible_to_source(0) == 0

    def test_search_bar_drawn_when_active(self):
        sel = OptionList(content=["item"], size=(20, 5))
        sel.enter_search()
        sel.search_handle_key("q")
        surface = Surface(20, 5)
        sel.paint(surface)
        bottom = "".join(c.char for c in surface._rows[4])
        assert "/q" in bottom
        theme = get_theme()
        assert surface._rows[4][0].fg == theme.fg_primary


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
        assert inp.cursor == 1

    def test_backspace(self):
        inp = InputLine()
        inp.insert("a")
        inp.insert("b")
        inp.backspace()
        assert inp.value == "a"
        assert inp.cursor == 1

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
        assert inp.cursor == 0

    def test_on_submit(self):
        called = []
        inp = InputLine(on_submit=lambda v: called.append(v))
        inp.insert("x")
        inp.handle_key("enter")
        assert called == ["x"]

    def test_overlay_submit_releases_focus_without_cancel(self, mocker):
        """Enter must end overlay editing (focus_release), not leave grab stuck."""
        submitted: list[str] = []
        cancelled: list[str] = []
        fm = mocker.Mock()
        mocker.patch(
            "pigit.termui.widgets.input_line.get_focus_manager",
            return_value=fm,
        )
        inp = InputLine(
            overlay_mode=True,
            visible=False,
            on_submit=lambda v: submitted.append(v),
            on_cancel=lambda: cancelled.append("cancel"),
        )
        inp._enter_overlay_mode()
        fm.focus_grab.assert_called_once_with(inp)
        assert inp.is_visible is True

        inp.insert("foo")
        inp.handle_key("enter")

        assert submitted == ["foo"]
        assert cancelled == []
        assert inp.is_visible is False
        fm.focus_release.assert_called_once()

    def test_overlay_esc_cancels_and_releases_focus(self, mocker):
        cancelled: list[str] = []
        fm = mocker.Mock()
        mocker.patch(
            "pigit.termui.widgets.input_line.get_focus_manager",
            return_value=fm,
        )
        inp = InputLine(
            overlay_mode=True,
            visible=False,
            on_cancel=lambda: cancelled.append("cancel"),
        )
        inp._enter_overlay_mode()
        inp.handle_key("esc")
        assert cancelled == ["cancel"]
        assert inp.is_visible is False
        fm.focus_release.assert_called_once()

    def test_on_cancel(self):
        called = []
        inp = InputLine(on_cancel=lambda: called.append("cancel"))
        inp.handle_key("esc")
        assert called == ["cancel"]

    def test_set_prompt(self):
        inp = InputLine(prompt="/")
        assert inp._prompt == "/"
        inp.set_prompt("git ")
        assert inp._prompt == "git "

    def test_tab_triggers_completion(self):
        inp = InputLine(candidate_provider=lambda text: ["foo", "bar", "baz"])
        inp.insert("f")
        inp.handle_key("tab")
        assert inp._showing_candidates is True
        assert inp._candidates == ["foo", "bar", "baz"]
        assert inp.value == "foo"

    def test_tab_with_no_provider_is_ignored(self):
        inp = InputLine()
        inp.insert("x")
        inp.handle_key("tab")
        assert inp.value == "x"
        assert not inp._showing_candidates

    def test_completion_navigate_up_down(self):
        inp = InputLine(candidate_provider=lambda text: ["a", "b", "c"])
        inp.handle_key("tab")
        assert inp.value == "a"
        inp.handle_key("down")
        assert inp.value == "b"
        inp.handle_key("down")
        assert inp.value == "c"
        inp.handle_key("up")
        assert inp.value == "b"

    def test_completion_enter_closes_without_submit(self):
        submitted = []
        inp = InputLine(
            candidate_provider=lambda text: ["alpha"],
            on_submit=lambda v: submitted.append(v),
        )
        inp.insert("a")
        inp.handle_key("tab")
        assert inp._showing_candidates
        inp.handle_key("enter")
        assert not inp._showing_candidates
        assert inp.value == "alpha"
        assert submitted == []
        # Second Enter triggers submit
        inp.handle_key("enter")
        assert submitted == ["alpha"]

    def test_completion_esc_restores_original(self):
        inp = InputLine(
            candidate_provider=lambda text: ["alpha"],
        )
        inp.set_value("orig")
        inp.handle_key("tab")
        assert inp.value == "alpha"
        inp.handle_key("esc")
        assert not inp._showing_candidates
        assert inp.value == "orig"

    def test_tab_next_candidate(self):
        inp = InputLine(
            candidate_provider=lambda text: ["a", "b", "c"],
        )
        inp.handle_key("tab")
        assert inp.value == "a"
        inp.handle_key("tab")
        assert inp.value == "b"
        inp.handle_key("tab")
        assert inp.value == "c"
        # does not wrap past end
        inp.handle_key("tab")
        assert inp.value == "c"

    def test_shift_tab_prev_candidate(self):
        inp = InputLine(
            candidate_provider=lambda text: ["a", "b", "c"],
        )
        inp.handle_key("tab")
        inp.handle_key("tab")
        inp.handle_key("tab")
        assert inp.value == "c"
        inp.handle_key("shift tab")
        assert inp.value == "b"
        inp.handle_key("shift tab")
        assert inp.value == "a"
        # does not wrap past start
        inp.handle_key("shift tab")
        assert inp.value == "a"

    def test_set_candidate_provider_none_disables_tab(self):
        inp = InputLine(
            candidate_provider=lambda text: ["x"],
        )
        inp.handle_key("tab")
        assert inp._showing_candidates
        inp.set_candidate_provider(None)
        inp.handle_key("tab")
        assert not inp._showing_candidates

    def test_render_with_candidates(self):
        from pigit.termui.surface import Surface
        from pigit.termui.theme import get_theme

        inp = InputLine(
            prompt="> ",
            candidate_provider=lambda text: ["abc"],
            size=(20, 1),
        )
        inp.set_value("a")
        inp.handle_key("tab")
        s = Surface(20, 1)
        inp.paint(s)
        assert s.lines()[0].startswith("> abc")
        theme = get_theme()
        row_cells = s.rows()[0]
        # Matched part "> a" stays normal
        assert row_cells[0].fg == theme.fg_primary
        assert row_cells[2].fg == theme.fg_primary
        # Suffix "bc" is dim
        assert row_cells[3].fg == theme.fg_dim
        assert row_cells[4].fg == theme.fg_dim

    def test_render_draws_block_cursor(self, mocker):
        from pigit.termui.theme import get_theme

        theme = get_theme()
        mock_surface = mocker.Mock()
        mock_surface.width = 10
        mock_surface.height = 1
        inp = InputLine(prompt="> ", size=(10, 1))
        inp.set_value("hi")
        inp._focus_level = 0  # mark as focused so cursor is drawn
        inp.paint(mock_surface)
        # Text is drawn via draw_text_rgb, then block cursor is drawn via draw_text_rgb
        # at cursor position (prompt_len + cursor = 2 + 2 = 4) as reverse video.
        assert mock_surface.draw_text_rgb.call_count == 2
        # First call: text row; second call: block cursor
        mock_surface.draw_text_rgb.assert_called_with(
            0, 4, " ", fg=theme.bg_chrome, bg=theme.fg_primary
        )

    def test_render_block_cursor_in_candidate_mode(self, mocker):
        from pigit.termui.theme import get_theme

        theme = get_theme()
        mock_surface = mocker.Mock()
        mock_surface.width = 12
        mock_surface.height = 1
        inp = InputLine(
            candidate_provider=lambda text: ["opt"],
            size=(12, 1),
        )
        inp.set_value("o")
        inp.handle_key("tab")
        inp._focus_level = 0  # mark as focused so cursor is drawn
        inp.paint(mock_surface)
        # Candidate mode draws prefix + dim suffix, then block cursor at end.
        calls = mock_surface.draw_text_rgb.call_args_list
        # Last call should be the block cursor at position 3 ("o" + "pt").
        assert (
            calls[-1]
            == (
                (
                    0,
                    3,
                    " ",
                ),
                {"fg": theme.bg_chrome, "bg": theme.fg_primary},
            )
            or calls[-1] == ((0, 3, " ", "DEFAULT_BG", "DEFAULT_FG"),)
            or calls[-1].args
            == (
                0,
                3,
                " ",
            )
            and calls[-1].kwargs == {"fg": theme.bg_chrome, "bg": theme.fg_primary}
        )

    def test_on_key_plain_text_editing(self):
        inp = InputLine()
        inp.handle_key("h")
        inp.handle_key("i")
        assert inp.value == "hi"
        inp.handle_key("backspace")
        assert inp.value == "h"
        inp.handle_key("left")
        assert inp.cursor == 0
        inp.handle_key("delete")
        assert inp.value == ""


class TestCheckList:
    def test_toggle_adds_to_checked(self):
        cl = CheckList(content=["a", "b", "c"])
        cl.toggle(0)
        assert cl.get_selected() == {0}
        cl.toggle(0)
        assert cl.get_selected() == set()

    def test_toggle_defaults_to_cursor(self):
        cl = CheckList(content=["a", "b", "c"])
        cl.curr_no = 1
        cl.toggle()
        assert cl.get_selected() == {1}

    def test_select_all_and_none(self):
        cl = CheckList(content=["a", "b"])
        cl.select_all()
        assert cl.get_selected() == {0, 1}
        cl.select_none()
        assert cl.get_selected() == set()

    def test_set_content_clamps_checked(self):
        cl = CheckList(content=["a", "b", "c"])
        cl.select_all()
        assert cl.get_selected() == {0, 1, 2}
        cl.set_content(["x"])
        assert cl.get_selected() == {0}

    def test_describe_row_renders_checkbox(self):
        cl = CheckList(content=["item"])
        left, main, _right = cl.describe_row(0, is_cursor=False)
        assert left[0].text == "·"
        assert main[0].text == "item"

    def test_describe_row_checked_and_cursor(self):
        cl = CheckList(content=["item"])
        cl.toggle(0)
        left, main, _right = cl.describe_row(0, is_cursor=True)
        assert left[0].text == "✓"
        assert main[0].text == "item"

    def test_describe_row_cursor_only(self):
        cl = CheckList(content=["item"])
        left, main, _right = cl.describe_row(0, is_cursor=True)
        assert left[0].text == "·"
        assert main[0].text == "item"
