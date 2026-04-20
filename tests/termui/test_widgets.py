# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_widgets.py
Description: Unit tests for StatusBar, InputLine, and ItemSelector widgets.
Author: Zev
Date: 2026-04-20
"""

import pytest

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
