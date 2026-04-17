# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_layer.py
Description: Tests for pigit.termui.layer.
Author: Zev
Date: 2026-04-17
"""

import pytest
from unittest.mock import MagicMock

from pigit.termui.layer import Layer, LayerKind, LayerStack
from pigit.termui.overlay_kinds import OverlayDispatchResult


class TestLayer:
    def test_push_and_top(self):
        layer = Layer(LayerKind.MODAL)
        surf = MagicMock()
        layer.push(surf)
        assert layer.top() is surf

    def test_pop_returns_latest(self):
        layer = Layer(LayerKind.MODAL)
        a, b = MagicMock(), MagicMock()
        layer.push(a)
        layer.push(b)
        assert layer.pop() is b
        assert layer.top() is a

    def test_clear(self):
        layer = Layer(LayerKind.MODAL)
        a, b = MagicMock(), MagicMock()
        layer.push(a)
        layer.push(b)
        layer.clear()
        a.hide.assert_not_called()
        b.hide.assert_not_called()
        assert layer.is_empty()


class TestLayerStack:
    def test_has_any_open_when_empty(self):
        stack = LayerStack()
        assert not stack.has_any_open()

    def test_push_modal_and_top(self):
        stack = LayerStack()
        surf = MagicMock()
        stack.push(LayerKind.MODAL, surf)
        assert stack.top(LayerKind.MODAL) is surf
        assert stack.has_any_open()

    def test_pop_modal(self):
        stack = LayerStack()
        surf = MagicMock()
        stack.push(LayerKind.MODAL, surf)
        assert stack.pop(LayerKind.MODAL) is surf
        assert stack.top(LayerKind.MODAL) is None

    def test_render_skips_closed(self):
        from pigit.termui.surface import Surface

        stack = LayerStack()
        open_surf = MagicMock()
        open_surf.open = True
        closed_surf = MagicMock()
        closed_surf.open = False
        stack.push(LayerKind.MODAL, open_surf)
        stack.push(LayerKind.TOAST, closed_surf)
        s = Surface(5, 2)
        stack.render(s)
        open_surf._render_surface.assert_called_once()
        closed_surf._render_surface.assert_not_called()

    def test_modal_intercepts_dispatch(self):
        stack = LayerStack()
        modal = MagicMock()
        modal.open = True
        modal.dispatch_overlay_key.return_value = OverlayDispatchResult.HANDLED_EXPLICIT
        stack.push(LayerKind.MODAL, modal)
        result = stack.dispatch("k")
        assert result is OverlayDispatchResult.HANDLED_EXPLICIT
        modal.dispatch_overlay_key.assert_called_once_with("k")

    def test_toast_layer_push_pop(self):
        stack = LayerStack()
        toast = MagicMock()
        stack.push(LayerKind.TOAST, toast)
        assert stack.top(LayerKind.TOAST) is toast
        assert stack.pop(LayerKind.TOAST) is toast
        assert stack.top(LayerKind.TOAST) is None

    def test_sheet_layer_push_pop(self):
        stack = LayerStack()
        sheet = MagicMock()
        stack.push(LayerKind.SHEET, sheet)
        assert stack.top(LayerKind.SHEET) is sheet
        assert stack.pop(LayerKind.SHEET) is sheet
        assert stack.top(LayerKind.SHEET) is None
