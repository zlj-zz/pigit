"""
Module: tests/termui/test_signal_widgets.py
Description: Tests for Signal-based auto-render in widgets.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

import pytest

from pigit.termui._runtime_context import (
    RuntimeContext,
    _runtime_ctx,
    set_render_request,
    reset_render_request,
)
from pigit.termui.widgets.check_list import CheckList
from pigit.termui.widgets.input_line import InputLine
from pigit.termui.widgets.item_list import ItemList


@pytest.fixture(autouse=True)
def _clear_runtime_context():
    """Reset runtime context before each test."""
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    yield
    _runtime_ctx.reset(token)


class TestItemListSignalRender:
    def test_curr_no_change_requests_render(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            sel = ItemList(content=["a", "b", "c"])
            sel.activate()
            sel.curr_no = 1
            assert len(render_calls) == 1
        finally:
            reset_render_request()

    def test_r_start_change_requests_render(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            sel = ItemList(content=["a", "b", "c"], size=(10, 1))
            sel.activate()
            sel._r_start = 1
            assert len(render_calls) == 1
        finally:
            reset_render_request()

    def test_next_changes_trigger_render(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            sel = ItemList(content=["a", "b", "c"])
            sel.activate()
            sel.next()
            assert len(render_calls) == 1
            sel.previous()
            assert len(render_calls) == 2
        finally:
            reset_render_request()

    def test_inactive_selector_does_not_request_render(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            sel = ItemList(content=["a", "b", "c"])
            # Not activated
            sel.curr_no = 1
            assert len(render_calls) == 0
        finally:
            reset_render_request()

    def test_destroy_unsubscribes(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            sel = ItemList(content=["a", "b", "c"])
            sel.activate()
            sel.destroy()
            sel.curr_no = 2
            assert len(render_calls) == 0
        finally:
            reset_render_request()


class TestCheckListSignalRender:
    def test_toggle_requests_render(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            cl = CheckList(content=["a", "b", "c"])
            cl.activate()
            cl.toggle(0)
            assert len(render_calls) == 1
            cl.toggle(0)
            assert len(render_calls) == 2
        finally:
            reset_render_request()

    def test_select_all_requests_render(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            cl = CheckList(content=["a", "b", "c"])
            cl.activate()
            cl.select_all()
            assert len(render_calls) == 1
        finally:
            reset_render_request()

    def test_select_none_requests_render(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            cl = CheckList(content=["a", "b", "c"])
            cl.activate()
            cl.select_all()
            render_calls.clear()
            cl.select_none()
            assert len(render_calls) == 1
        finally:
            reset_render_request()

    def test_destroy_unsubscribes(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            cl = CheckList(content=["a", "b", "c"])
            cl.activate()
            cl.destroy()
            cl.toggle(0)
            assert len(render_calls) == 0
        finally:
            reset_render_request()


class TestInputLineSignalRender:
    def test_insert_requests_render(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            inp = InputLine()
            inp.activate()
            inp.insert("a")
            # insert() changes both value and cursor -> 2 requests (coalesced to 1 render)
            assert len(render_calls) == 2
        finally:
            reset_render_request()

    def test_backspace_requests_render(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            inp = InputLine()
            inp.activate()
            inp.set_value("ab")
            render_calls.clear()
            inp.backspace()
            # backspace() changes both value and cursor -> 2 requests
            assert len(render_calls) == 2
        finally:
            reset_render_request()

    def test_cursor_move_requests_render(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            inp = InputLine()
            inp.activate()
            inp.set_value("ab")
            render_calls.clear()
            inp.cursor_left()
            assert len(render_calls) == 1
        finally:
            reset_render_request()

    def test_inactive_input_does_not_request_render(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            inp = InputLine()
            # Not activated
            inp.insert("a")
            assert len(render_calls) == 0
        finally:
            reset_render_request()

    def test_destroy_unsubscribes(self):
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            inp = InputLine()
            inp.activate()
            inp.destroy()
            inp.insert("a")
            assert len(render_calls) == 0
        finally:
            reset_render_request()
