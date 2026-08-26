# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_mouse.py
Description: Tests for SGR mouse parsing, hit-testing, and mouse dispatch.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

from io import StringIO
from unittest import mock
from unittest.mock import MagicMock

import pytest

from pigit.termui.component import Component
from pigit.termui._layer import LayerKind
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind, parse_sgr_mouse
from pigit.termui.root import ComponentRoot
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx
from pigit.termui.containers import Column, Row, TabView
from pigit.termui.input import KeyboardInput
from pigit.termui.widgets.option_list import OptionList
from pigit.termui.widgets.text_browser import TextBrowser
from pigit.termui.widgets.popup import Popup


@pytest.fixture(autouse=True)
def _runtime_context():
    """Provide a fresh RuntimeContext for mouse dispatch tests."""
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    yield
    _runtime_ctx.reset(token)


class _Leaf(Component):
    """A concrete leaf component for hit-testing."""

    def paint(self, surface):
        pass

    def refresh(self):
        pass


class _FakeTTY(StringIO):
    def isatty(self):
        return True

    def fileno(self):
        return 0

    def flush(self):
        pass


# ---------------------------------------------------------------------------
# SGR mouse parsing
# ---------------------------------------------------------------------------


class TestParseSgrMouse:
    def test_left_press(self):
        ev = parse_sgr_mouse(b"\x1b[<0;5;10M")
        assert ev == MouseEvent(5, 10, MouseButton.LEFT, MouseKind.PRESS)

    def test_right_press(self):
        ev = parse_sgr_mouse(b"\x1b[<2;5;10M")
        assert ev.button is MouseButton.RIGHT
        assert ev.kind is MouseKind.PRESS

    def test_release(self):
        ev = parse_sgr_mouse(b"\x1b[<3;5;10m")
        assert ev.kind is MouseKind.RELEASE
        assert ev.button is MouseButton.NONE

    def test_wheel_up(self):
        ev = parse_sgr_mouse(b"\x1b[<64;5;10M")
        assert ev.button is MouseButton.WHEEL_UP
        assert ev.kind is MouseKind.PRESS

    def test_wheel_down(self):
        ev = parse_sgr_mouse(b"\x1b[<65;5;10M")
        assert ev.button is MouseButton.WHEEL_DOWN

    def test_wheel_left_and_right_are_distinct(self):
        left = parse_sgr_mouse(b"\x1b[<66;5;10M")
        right = parse_sgr_mouse(b"\x1b[<67;5;10M")
        assert left.button is MouseButton.WHEEL_LEFT
        assert right.button is MouseButton.WHEEL_RIGHT

    def test_wheel_release_is_none(self):
        assert parse_sgr_mouse(b"\x1b[<64;5;10m") is None

    def test_wheel_motion_is_none(self):
        # 64 | 0x20 = 96: wheel-up with motion flag set.
        assert parse_sgr_mouse(b"\x1b[<96;5;10M") is None

    def test_drag_motion(self):
        ev = parse_sgr_mouse(b"\x1b[<32;5;10M")
        assert ev.button is MouseButton.LEFT
        assert ev.motion is True

    def test_modifiers(self):
        assert parse_sgr_mouse(b"\x1b[<4;5;10M").shift is True
        assert parse_sgr_mouse(b"\x1b[<8;5;10M").alt is True
        assert parse_sgr_mouse(b"\x1b[<16;5;10M").ctrl is True

    @pytest.mark.parametrize(
        "data",
        [
            b"",
            b"xyz",
            b"\x1b[<0;5M",  # missing a coordinate
            b"\x1b[<a;b;cM",  # non-numeric
            b"\x1b[<0;5;10X",  # wrong final byte
        ],
    )
    def test_malformed_returns_none(self, data):
        assert parse_sgr_mouse(data) is None


# ---------------------------------------------------------------------------
# Input pipeline: bytes -> MouseEvent
# ---------------------------------------------------------------------------


class TestMouseInputPipeline:
    def test_consume_one_emits_mouse_event(self):
        ki = KeyboardInput()
        ki._buffer = bytearray(b"\x1b[<0;5;10M")
        ev, n = ki._consume_one()
        assert isinstance(ev, MouseEvent)
        assert ev.col == 5 and ev.row == 10
        assert n == 10
        assert len(ki._buffer) == 0

    def test_consume_one_mouse_not_confused_with_arrow(self):
        ki = KeyboardInput()
        ki._buffer = bytearray(b"\x1b[A")
        key, n = ki._consume_one()
        assert key == "up"
        assert n == 3

    def test_read_keys_emits_mouse_event(self):
        kb = KeyboardInput(read_hook=lambda _t: b"\x1b[<0;5;10M")
        result = kb.read_keys(0.01)
        assert len(result) == 1
        assert isinstance(result[0], MouseEvent)

    def test_wheel_release_dropped_from_pipeline(self):
        kb = KeyboardInput(read_hook=lambda _t: b"\x1b[<64;5;10m")
        assert kb.read_keys(0.01) == []


# ---------------------------------------------------------------------------
# Hit-testing
# ---------------------------------------------------------------------------


class TestHitTest:
    def test_leaf_returns_self_with_local_coords(self):
        leaf = _Leaf()
        leaf._size = (10, 5)
        hit = leaf._hit_test(3, 2)
        assert hit == (leaf, 3, 2)

    def test_column_nests_local_coords(self):
        leaf = _Leaf()
        col = Column(children=[leaf], heights=["flex"])
        col.resize((10, 5))
        hit = col._hit_test(3, 2)
        assert hit[0] is leaf
        assert hit[1] == 3
        assert hit[2] == 2

    def test_row_axis(self):
        a = _Leaf()
        b = _Leaf()
        row = Row(children=[a, b], widths=[5, 5])
        row.resize((10, 3))
        assert row._hit_test(2, 1)[0] is a  # col 2 -> first half
        assert row._hit_test(7, 1)[0] is b  # col 7 -> second half

    def test_hit_outside_children_returns_self(self):
        parent = _Leaf()
        leaf = _Leaf()
        parent.children = [leaf]
        leaf._size = (3, 2)
        leaf.x = 1  # row
        leaf.y = 1  # col
        # Point at col=8, row=3 falls outside the leaf (cols 1-3, rows 1-2).
        assert parent._hit_test(8, 3) == (parent, 8, 3)

    def test_tabview_hits_active_only(self):
        active = _Leaf()
        inactive = _Leaf()
        tv = TabView(children=[active, inactive])
        tv.resize((10, 5))
        assert tv._hit_test(3, 3)[0] is active

    def test_popup_delegates_to_child_with_offset(self):
        child = _Leaf()
        popup = Popup(child)
        child._size = (10, 5)
        child.x = 2  # row
        child.y = 3  # col
        hit = popup._hit_test(4, 3)
        assert hit[0] is child
        assert hit[1] == 2  # 4 - (3 - 1)
        assert hit[2] == 2  # 3 - (2 - 1)

    def test_popup_layout_centers_child_with_1_based_coords(self):
        class _Body(_Leaf):
            _outer_w = 20
            outer_row_count = 6

        child = _Body()
        popup = Popup(child)
        popup.resize((40, 20))
        # Center offsets (0-based): row=(20-6)//2=7, col=(40-20)//2=10.
        # Stored as 1-based x=row/y=col, consistent with Column/Row layout.
        assert child.x == 8
        assert child.y == 11
        assert child._size == (20, 6)


# ---------------------------------------------------------------------------
# OptionList mouse handling
# ---------------------------------------------------------------------------


class TestOptionListMouse:
    def _list(self):
        lst = OptionList()
        lst.set_content(["a", "b", "c", "d"])
        lst.resize((10, 4))
        return lst

    def test_click_selects_row(self):
        lst = self._list()
        ev = MouseEvent(col=2, row=3, button=MouseButton.LEFT, kind=MouseKind.PRESS)
        assert lst.handle_mouse(ev) is True
        assert lst.curr_no == 2  # local row 3 -> content index 2

    def test_wheel_scrolls(self):
        lst = self._list()
        lst.curr_no = 0
        down = MouseEvent(1, 1, MouseButton.WHEEL_DOWN, MouseKind.PRESS)
        assert lst.handle_mouse(down) is True
        assert lst.curr_no == 1

    def test_release_ignored(self):
        lst = self._list()
        ev = MouseEvent(col=2, row=2, button=MouseButton.LEFT, kind=MouseKind.RELEASE)
        assert lst.handle_mouse(ev) is False
        assert lst.curr_no == 0


# ---------------------------------------------------------------------------
# TextBrowser mouse handling (diff viewer wheel scroll)
# ---------------------------------------------------------------------------


class TestTextBrowserMouse:
    def _browser(self):
        browser = TextBrowser(content=["l0", "l1", "l2", "l3", "l4", "l5", "l6", "l7"])
        browser.resize((10, 3))
        return browser

    def test_wheel_scrolls_down_and_up(self):
        browser = self._browser()
        assert browser._i == 0
        down = MouseEvent(1, 1, MouseButton.WHEEL_DOWN, MouseKind.PRESS)
        assert browser.handle_mouse(down) is True
        assert browser.scroll_i == TextBrowser.WHEEL_SCROLL_LINES
        up = MouseEvent(1, 1, MouseButton.WHEEL_UP, MouseKind.PRESS)
        assert browser.handle_mouse(up) is True
        assert browser._i == 0

    def test_release_ignored(self):
        browser = self._browser()
        ev = MouseEvent(1, 1, MouseButton.WHEEL_DOWN, MouseKind.RELEASE)
        assert browser.handle_mouse(ev) is False
        assert browser._i == 0

    def test_horizontal_wheel_ignored(self):
        browser = self._browser()
        ev = MouseEvent(1, 1, MouseButton.WHEEL_LEFT, MouseKind.PRESS)
        assert browser.handle_mouse(ev) is False
        assert browser._i == 0


# ---------------------------------------------------------------------------
# Session mouse reporting
# ---------------------------------------------------------------------------


class TestSessionMouse:
    def test_enter_enables_mouse(self):
        from pigit.termui._session import Session

        session = Session(stdin=_FakeTTY(), stdout=_FakeTTY())
        with mock.patch("sys.platform", "linux"):
            with mock.patch.dict(
                "sys.modules", {"termios": mock.Mock(), "tty": mock.Mock()}
            ):
                session.__enter__()
        out = session.stdout.getvalue()
        assert "\033[?1002h" in out
        assert "\033[?1006h" in out

    def test_exit_disables_mouse(self):
        from pigit.termui._session import Session

        session = Session(stdin=_FakeTTY(), stdout=_FakeTTY())
        session._old_termios = ["mock"]
        with mock.patch("sys.platform", "linux"):
            with mock.patch.dict("sys.modules", {"termios": mock.Mock()}):
                session.__exit__(None, None, None)
        out = session.stdout.getvalue()
        assert "\033[?1002l" in out
        assert "\033[?1006l" in out


# ---------------------------------------------------------------------------
# ComponentRoot mouse routing
# ---------------------------------------------------------------------------


class _DummyBody(Component):
    def paint(self, surface):
        pass

    def refresh(self):
        pass


class TestRootMouse:
    def _mouse(self):
        return MouseEvent(col=1, row=1, button=MouseButton.LEFT, kind=MouseKind.PRESS)

    def test_modal_swallows_click_outside(self):
        root = ComponentRoot(_DummyBody())
        popup = MagicMock()
        popup.open = True
        popup._hit_test.return_value = None
        root._layer_stack.push(LayerKind.MODAL, popup)
        assert root._handle_mouse(self._mouse()) is True
        popup._hit_test.assert_called_once()

    def test_body_click_dispatches_to_body(self):
        root = ComponentRoot(_DummyBody())
        body = root.body
        body._hit_test = MagicMock(return_value=(body, 1, 1))
        body.handle_mouse = MagicMock(return_value=False)
        assert root._handle_mouse(self._mouse()) is True
        body.handle_mouse.assert_called_once()

    def test_focus_component_switches_column_focus_index(self):
        a = _Leaf()
        b = _Leaf()
        col = Column(children=[a, b], heights=["flex", "flex"], focus_index=0)
        root = ComponentRoot(col)
        root.resize((10, 6))
        root.focus_component(b)
        assert col._focus_index == 1
        assert root._focus_manager.get_focus_leaf() is b

    def test_focus_component_non_focusable_does_not_steal(self):
        header = _Leaf()
        a = _Leaf()
        b = _Leaf()
        col = Column(children=[a, b], heights=["flex", "flex"], focus_index=0)
        outer = Column(children=[header, col], heights=[1, "flex"])
        root = ComponentRoot(outer)
        root.resize((10, 8))
        before = root._focus_manager.get_focus_leaf()
        root.focus_component(header)
        assert root._focus_manager.get_focus_leaf() is before

    def test_modal_click_closing_restores_body_focus(self):
        root = ComponentRoot(_DummyBody())
        root.resize((80, 24))

        class _ClosingPopup(Component):
            open = True

            def _hit_test(self, col, row):
                return self, col, row

            def handle_mouse(self, event):
                root._layer_stack.pop(LayerKind.MODAL)
                self.open = False
                return True

        popup = _ClosingPopup()
        root._layer_stack.push(LayerKind.MODAL, popup)
        root._focus_manager.set_focus_chain(popup)

        assert root._handle_mouse(self._mouse()) is True
        assert root._focus_manager.get_focus_leaf() is root.body
