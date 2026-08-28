# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_popup.py
Description: Popup offset clamp and dismiss_on_miss mouse contract.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx, set_overlay_host
from pigit.termui.component import Component
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.root import ComponentRoot
from pigit.termui.types import LayerKind
from pigit.termui.widgets.popup import Popup


class _FramedChild(Component):
    """Minimal Popup child that satisfies the ``_outer_w`` layout contract."""

    def __init__(self, outer_w: int = 20, outer_h: int = 6) -> None:
        super().__init__()
        self._outer_w = outer_w
        self.outer_row_count = outer_h


class _Body(Component):
    """Empty body for ComponentRoot."""


def test_popup_offset_clamps_to_terminal():
    child = _FramedChild(20, 6)
    popup = Popup(child, offset=(100, 100))
    popup.resize((40, 20))
    # th-oh=14, tw-ow=20 → clamped to those maxima; 1-based x/y = +1.
    assert child.x == 15
    assert child.y == 21
    assert child._size == (20, 6)


def test_popup_offset_none_still_centers():
    child = _FramedChild(20, 6)
    popup = Popup(child, offset=None)
    popup.resize((40, 20))
    assert child.x == 8
    assert child.y == 11


def _open_modal(root: ComponentRoot, popup: Popup) -> None:
    set_overlay_host(root)
    popup.resize(root._size)
    popup.show()
    popup.begin_session()


def test_dismiss_on_miss_closes_and_restores_focus():
    token = _runtime_ctx.set(RuntimeContext())
    try:
        body = _Body()
        body.resize((40, 20))
        root = ComponentRoot(body)
        root.resize((40, 20))
        root.mount()

        child = _FramedChild(10, 4)
        popup = Popup(child, offset=(2, 2), dismiss_on_miss=True)
        _open_modal(root, popup)
        assert popup.open is True
        assert root._layer_stack.top(LayerKind.MODAL) is popup

        miss = MouseEvent(col=39, row=19, button=MouseButton.LEFT, kind=MouseKind.PRESS)
        assert root._handle_mouse(miss) is True
        assert popup.open is False
        assert root._layer_stack.top(LayerKind.MODAL) is None
        assert root._focus_manager.get_focus_leaf() is body
    finally:
        _runtime_ctx.reset(token)


def test_dismiss_on_miss_false_keeps_modal_open():
    token = _runtime_ctx.set(RuntimeContext())
    try:
        body = _Body()
        body.resize((40, 20))
        root = ComponentRoot(body)
        root.resize((40, 20))
        root.mount()

        child = _FramedChild(10, 4)
        popup = Popup(child, offset=(2, 2), dismiss_on_miss=False)
        _open_modal(root, popup)

        miss = MouseEvent(col=39, row=19, button=MouseButton.LEFT, kind=MouseKind.PRESS)
        assert root._handle_mouse(miss) is True
        assert popup.open is True
        assert root._layer_stack.top(LayerKind.MODAL) is popup
    finally:
        _runtime_ctx.reset(token)
