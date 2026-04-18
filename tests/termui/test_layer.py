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

    def test_layer_stack_dispatch_toast_dropped(self):
        """TOAST layer overlays do not intercept dispatch; keys fall through."""
        stack = LayerStack()
        toast = MagicMock()
        toast.open = True
        toast.dispatch_overlay_key.return_value = OverlayDispatchResult.DROPPED_UNBOUND
        stack.push(LayerKind.TOAST, toast)
        result = stack.dispatch("k")
        assert result is OverlayDispatchResult.DROPPED_UNBOUND
        toast.dispatch_overlay_key.assert_called_once_with("k")

    def test_layer_stack_dispatch_sheet_delegates(self):
        """SHEET layer overlays participate in dispatch when they handle keys."""
        stack = LayerStack()
        sheet = MagicMock()
        sheet.open = True
        sheet.dispatch_overlay_key.return_value = OverlayDispatchResult.HANDLED_EXPLICIT
        stack.push(LayerKind.SHEET, sheet)
        result = stack.dispatch("k")
        assert result is OverlayDispatchResult.HANDLED_EXPLICIT
        sheet.dispatch_overlay_key.assert_called_once_with("k")

    def test_layer_stack_dispatch_priority_modal_over_sheet(self):
        """When both MODAL and SHEET are present, MODAL takes precedence."""
        stack = LayerStack()
        modal = MagicMock()
        modal.open = True
        modal.dispatch_overlay_key.return_value = OverlayDispatchResult.HANDLED_EXPLICIT
        sheet = MagicMock()
        sheet.open = True
        stack.push(LayerKind.SHEET, sheet)
        stack.push(LayerKind.MODAL, modal)
        result = stack.dispatch("k")
        assert result is OverlayDispatchResult.HANDLED_EXPLICIT
        modal.dispatch_overlay_key.assert_called_once_with("k")
        sheet.dispatch_overlay_key.assert_not_called()

    def test_layer_stack_pop_does_not_call_hide(self):
        """LayerStack.pop returns the overlay without calling hide() — lifecycle is caller's responsibility."""
        stack = LayerStack()
        overlay = MagicMock()
        stack.push(LayerKind.MODAL, overlay)
        result = stack.pop(LayerKind.MODAL)
        assert result is overlay
        overlay.hide.assert_not_called()

    def test_layer_clear_does_not_call_hide(self):
        """Layer.clear removes all surfaces without calling hide() — lifecycle is caller's responsibility."""
        layer = Layer(LayerKind.MODAL)
        a, b = MagicMock(), MagicMock()
        layer.push(a)
        layer.push(b)
        layer.clear()
        a.hide.assert_not_called()
        b.hide.assert_not_called()
        assert layer.is_empty()

    def test_layer_pop_empty_returns_none(self):
        layer = Layer(LayerKind.MODAL)
        assert layer.pop() is None

    def test_layer_is_empty_true(self):
        layer = Layer(LayerKind.MODAL)
        assert layer.is_empty()

    def test_layer_is_empty_false(self):
        layer = Layer(LayerKind.MODAL)
        layer.push(MagicMock())
        assert not layer.is_empty()

    def test_layer_stack_resize_skips_overlay_without_resize(self):
        stack = LayerStack()
        overlay = MagicMock(spec=[])
        stack.push(LayerKind.TOAST, overlay)
        # Should not raise even though overlay has no resize method
        stack.resize((40, 20))

    def test_layer_stack_dispatch_sheet_dropped_then_toast_dropped(self):
        """SHEET drops, then TOAST drops — both continue to fallthrough."""
        stack = LayerStack()
        sheet = MagicMock()
        sheet.open = True
        sheet.dispatch_overlay_key.return_value = OverlayDispatchResult.DROPPED_UNBOUND
        toast = MagicMock()
        toast.open = True
        toast.dispatch_overlay_key.return_value = OverlayDispatchResult.DROPPED_UNBOUND
        stack.push(LayerKind.SHEET, sheet)
        stack.push(LayerKind.TOAST, toast)
        result = stack.dispatch("k")
        assert result is OverlayDispatchResult.DROPPED_UNBOUND
        sheet.dispatch_overlay_key.assert_called_once_with("k")
        toast.dispatch_overlay_key.assert_called_once_with("k")

    def test_layer_stack_resize_calls_overlay_resize(self):
        stack = LayerStack()
        overlay = MagicMock()
        stack.push(LayerKind.TOAST, overlay)
        stack.resize((40, 20))
        overlay.resize.assert_called_once_with((40, 20))


class TestLayerDispatchHost:
    def test_force_close_with_no_top_does_nothing(self):
        from pigit.termui.layer import _LayerDispatchHost

        stack = LayerStack()
        host = _LayerDispatchHost(stack)
        host.force_close_overlay_after_error()
        # No exception; stack remains empty
        assert stack.top(LayerKind.MODAL) is None

    def test_force_close_with_no_hide_attribute(self):
        from pigit.termui.layer import _LayerDispatchHost

        stack = LayerStack()
        overlay = MagicMock(spec=[])
        stack.push(LayerKind.MODAL, overlay)
        host = _LayerDispatchHost(stack)
        host.force_close_overlay_after_error()
        assert stack.top(LayerKind.MODAL) is None

    def test_force_close_without_reset_state(self):
        from pigit.termui.layer import _LayerDispatchHost

        stack = LayerStack()
        overlay = MagicMock()
        del overlay.reset_state
        stack.push(LayerKind.MODAL, overlay)
        host = _LayerDispatchHost(stack)
        host.force_close_overlay_after_error()
        overlay.hide.assert_called_once()
        assert stack.top(LayerKind.MODAL) is None


class TestComponentRootPopLayer:
    """ComponentRoot._pop_layer calls hide() after LayerStack.pop — the caller-level lifecycle hook."""

    def test_component_root_pop_layer_calls_hide(self):
        from pigit.termui.root import ComponentRoot

        body = MagicMock()
        body._render_surface = MagicMock()
        root = ComponentRoot(body)
        overlay = MagicMock()
        root._layer_stack.push(LayerKind.TOAST, overlay)
        root._pop_layer(LayerKind.TOAST)
        overlay.hide.assert_called_once()

    def test_component_root_force_close_after_error_calls_hide(self):
        from pigit.termui.root import ComponentRoot

        body = MagicMock()
        root = ComponentRoot(body)
        overlay = MagicMock()
        overlay.reset_state = MagicMock()
        root._layer_stack.push(LayerKind.MODAL, overlay)
        root.force_close_overlay_after_error()
        overlay.hide.assert_called_once()
        overlay.reset_state.assert_called_once()
