# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_tab_view.py
Description: Tests for pigit.termui.components TabView.
Author: Zev
Date: 2026-04-17
"""

import logging
import pytest
from unittest.mock import MagicMock

from pigit.termui._component_base import Component, ComponentError
from pigit.termui._component_layouts import TabView
from pigit.termui.types import ActionLiteral
from pigit.termui._component_widgets import LineTextBrowser, ItemSelector
from pigit.termui._component_mixins import LazyLoadMixin
from pigit.termui._surface import Surface


class _Leaf(Component):
    def fresh(self):
        pass

    def _render_surface(self, surface):
        pass


class _LineBrowser(LineTextBrowser):
    def fresh(self):
        pass


class _Selector(ItemSelector):
    pass


class TestComponentBase:
    def test_emit_to_parent(self):
        parent = _Leaf()
        child = _Leaf()
        child.parent = parent
        parent.accept = MagicMock()
        child.emit(ActionLiteral.goto, target="x")
        parent.accept.assert_called_once_with(ActionLiteral.goto, target="x")

    def test_emit_without_parent_raises(self):
        child = _Leaf()
        with pytest.raises(AssertionError, match="Has no parent"):
            child.emit(ActionLiteral.goto, target="x")

    def test_notify_children(self):
        a, b = _Leaf(), _Leaf()
        parent = _Leaf(children={"a": a, "b": b})
        a.parent = parent
        b.parent = parent
        a.update = MagicMock()
        b.update = MagicMock()
        parent.notify(ActionLiteral.goto, target="x")
        a.update.assert_called_once_with(ActionLiteral.goto, target="x")
        b.update.assert_called_once_with(ActionLiteral.goto, target="x")

    def test_notify_without_children_raises(self):
        leaf = _Leaf()
        leaf.children = None
        with pytest.raises(AssertionError, match="Has no children"):
            leaf.notify(ActionLiteral.goto, target="x")

    def test_resize_propagates_to_children(self):
        child = _Leaf()
        child.resize = MagicMock(wraps=child.resize)
        parent = TabView(children=[child])
        parent.resize((10, 5))
        child.resize.assert_called_once_with((10, 5))

    def test_handle_event_binding(self):
        class _Bound(_Leaf):
            BINDINGS = [("x", "on_x")]

            def on_x(self):
                self.called = True

        leaf = _Bound()
        leaf._handle_event("x")
        assert leaf.called is True

    def test_handle_event_on_key(self):
        leaf = _Leaf()
        leaf.on_key = MagicMock()
        leaf._handle_event("k")
        leaf.on_key.assert_called_once_with("k")

    def test_has_overlay_open_default(self):
        assert _Leaf().has_overlay_open() is False

    def test_try_dispatch_overlay_default(self):
        from pigit.termui.types import OverlayDispatchResult

        assert _Leaf().try_dispatch_overlay("k") is OverlayDispatchResult.DROPPED_UNBOUND

    def test_get_help_entries_derives_from_bindings(self):
        class _Bound(_Leaf):
            BINDINGS = [("x", "on_x")]

            def on_x(self):
                """Do the thing."""
                pass

        entries = _Bound().get_help_entries()
        assert any("x" == e[0] and "Do the thing." in e[1] for e in entries)

    def test_nearest_overlay_host_walks_up(self):
        class _MockHost(_Leaf):
            def begin_popup_session(self, popup):
                pass

            def end_popup_session(self):
                pass

        host = _MockHost()
        mid = _Leaf()
        mid.parent = host
        leaf = _Leaf()
        leaf.parent = mid
        assert leaf.nearest_overlay_host() is host

    def test_nearest_overlay_host_none(self):
        leaf = _Leaf()
        assert leaf.nearest_overlay_host() is None


class TestTabView:
    def test_accept_goto_switches_child(self):
        a, b = _Leaf(), _Leaf()
        a.update = MagicMock()
        b.update = MagicMock()
        cont = TabView(children=[a, b], start=a)
        cont.accept(ActionLiteral.goto, target=b)
        assert b.is_activated() is True
        assert a.is_activated() is False
        b.update.assert_called_once_with(ActionLiteral.goto, target=b)

    def test_accept_goto_missing_logs_warning(self, caplog):
        a = _Leaf()
        cont = TabView(children=[a])
        missing = _Leaf()
        with caplog.at_level(logging.WARNING):
            cont.accept(ActionLiteral.goto, target=missing)
        assert "not found in children" in caplog.text

    def test_accept_unsupported_action_logs_warning(self, caplog):
        cont = TabView(children=[_Leaf()])
        with caplog.at_level(logging.WARNING):
            cont.accept(ActionLiteral.goto, target="/z")
        assert "unsupported action" in caplog.text or "not found" in caplog.text

    def test_handle_event_shortcuts_routing(self):
        a, b = _Leaf(), _Leaf()
        a._handle_event = MagicMock()
        b._handle_event = MagicMock()
        cont = TabView(
            children=[a, b],
            start=a,
            shortcuts={"1": b},
        )
        cont._handle_event("1")
        b._handle_event.assert_not_called()
        assert b.is_activated() is True

    def test_handle_event_delegates_to_active(self):
        a = _Leaf()
        a._handle_event = MagicMock()
        cont = TabView(children=[a])
        cont._handle_event("k")
        a._handle_event.assert_called_once_with("k")


class TestLineTextBrowser:
    def test_render_with_content(self):
        browser = _LineBrowser(content=["a", "b", "c"], size=(2, 2))
        s = Surface(2, 2)
        browser._render_surface(s)
        assert s.lines()[0] == "a "
        assert s.lines()[1] == "b "

    def test_render_none_content_is_noop(self):
        browser = _LineBrowser(size=(2, 2))
        s = Surface(2, 2)
        browser._render_surface(s)
        assert s.lines() == ["  ", "  "]

    def test_resize_updates_max_line(self):
        browser = _LineBrowser(content=["a"] * 10)
        browser.resize((5, 3))
        assert browser._max_line == 3


class TestItemSelector:
    def test_cursor_length_check(self):
        class _Bad(_Selector):
            CURSOR = "xx"

        with pytest.raises(ComponentError, match="error"):
            _Bad()

    def test_next_forward_scroll(self):
        sel = _Selector(content=["a", "b", "c", "d"], size=(5, 2))
        sel.next(2)
        assert sel.curr_no == 2
        assert sel._r_start == 2
        sel.next(1)
        assert sel.curr_no == 3
        assert sel._r_start == 2

    def test_forward_scroll(self):
        sel = _Selector(content=["a", "b", "c", "d"], size=(5, 2))
        sel.curr_no = 3
        sel._r_start = 2
        sel.forward(2)
        assert sel.curr_no == 1
        assert sel._r_start == 0

    def test_next_out_of_bounds_is_ignored(self):
        sel = _Selector(content=["a", "b"], size=(5, 2))
        sel.curr_no = 1
        sel.next(1)
        assert sel.curr_no == 1

    def test_forward_out_of_bounds_is_ignored(self):
        sel = _Selector(content=["a", "b"], size=(5, 2))
        sel.curr_no = 0
        sel.forward(1)
        assert sel.curr_no == 0

    def test_render_cursor(self):
        sel = _Selector(content=["a", "b"], size=(5, 2))
        s = Surface(5, 2)
        sel._render_surface(s)
        assert s.lines()[0] == "\u2192a   "
        assert s.lines()[1] == " b   "


class TestLazyLoadMixin:
    def test_resize_when_activated_calls_fresh(self):
        class _Panel(LazyLoadMixin, _Leaf):
            def __init__(self):
                super().__init__()
                self.fresh_calls = 0

            def fresh(self):
                self.fresh_calls += 1

        panel = _Panel()
        panel.activate()
        panel.resize((10, 5))
        assert panel.fresh_calls == 1
        assert panel._panel_loaded is True

    def test_resize_when_inactive_sets_placeholder(self):
        class _Panel(LazyLoadMixin, _Leaf):
            def set_content(self, content):
                self._placeholder = content

        panel = _Panel()
        panel.deactivate()
        panel.resize((10, 5))
        assert panel._placeholder == ["Loading..."]
        assert panel.curr_no == 0
        assert panel._r_start == 0
