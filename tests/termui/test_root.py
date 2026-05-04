# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_root.py
Description: Tests for pigit.termui.root.
Author: Zev
Date: 2026-04-17
"""

import pytest
from unittest.mock import MagicMock

from pigit.termui._component_base import Component
from pigit.termui._overlay_components import ToastPosition
from pigit.termui._layer import LayerKind
from pigit.termui._root import ComponentRoot
from pigit.termui.types import OverlayDispatchResult


class DummyBody(Component):
    NAME = "dummy"

    def _render_surface(self, surface):
        pass

    def refresh(self):
        pass


class TestComponentRoot:
    def test_body_parent_is_root(self):
        body = DummyBody()
        root = ComponentRoot(body)
        assert root.body is body
        assert body.parent is root

    def test_overlay_kind_none_by_default(self):
        root = ComponentRoot(DummyBody())
        assert not root.has_overlay_open()

    def test_layer_push_pop_modal(self):
        root = ComponentRoot(DummyBody())
        popup = MagicMock()
        popup.open = True
        root._layer_stack.push(LayerKind.MODAL, popup)
        assert root.has_overlay_open()
        assert root._layer_stack.top(LayerKind.MODAL) is popup
        root._layer_stack.pop(LayerKind.MODAL)
        popup.hide.assert_not_called()
        assert not root.has_overlay_open()
        assert root._layer_stack.top(LayerKind.MODAL) is None

    def test_handle_event_modal_intercepts(self):
        root = ComponentRoot(DummyBody())
        body = root.body
        body._handle_event = MagicMock()
        popup = MagicMock()
        popup.open = True
        popup.parent = None
        popup.dispatch_overlay_key.return_value = OverlayDispatchResult.HANDLED_EXPLICIT
        root._layer_stack.push(LayerKind.MODAL, popup)
        root._handle_event("k")
        popup.dispatch_overlay_key.assert_called_once_with("k")
        body._handle_event.assert_not_called()

    def test_handle_event_passthrough_to_body(self):
        root = ComponentRoot(DummyBody())
        body = root.body
        body._handle_event = MagicMock()
        root._handle_event("k")
        body._handle_event.assert_called_once_with("k")

    def test_force_close_overlay_after_error(self):
        root = ComponentRoot(DummyBody())
        popup = MagicMock()
        popup.open = True
        root._layer_stack.push(LayerKind.MODAL, popup)
        root.force_close_overlay_after_error()
        popup.hide.assert_called_once()
        assert not root.has_overlay_open()
        assert root._layer_stack.top(LayerKind.MODAL) is None

    def test_accept_forwards_to_body(self):
        from pigit.termui.types import ActionEventType

        root = ComponentRoot(DummyBody())
        root.body.accept = MagicMock()
        root.accept(ActionEventType.goto, target="x")
        root.body.accept.assert_called_once_with(ActionEventType.goto, target="x")

    def test_fresh_does_not_raise(self):
        root = ComponentRoot(DummyBody())
        root.refresh()

    def test_show_toast(self):
        root = ComponentRoot(DummyBody())
        root.resize((80, 24))
        toast = root.show_toast("hello", duration=1.5)
        assert root._layer_stack.top(LayerKind.TOAST) is toast
        assert len(toast._segments) == 1
        assert toast._segments[0].text == "hello"
        assert toast.duration == 1.5

    def test_show_toast_with_position(self):
        """验证 show_toast 支持 position 参数"""
        root = ComponentRoot(DummyBody())
        root.resize((80, 24))
        toast = root.show_toast(
            "hello", duration=1.5, position=ToastPosition.BOTTOM_LEFT
        )
        assert toast._position == ToastPosition.BOTTOM_LEFT

    def test_show_toast_singleton_replaces_existing(self):
        """验证新 Toast 替换旧 Toast（单例模式）"""
        root = ComponentRoot(DummyBody())
        root.resize((80, 24))
        toast1 = root.show_toast("first", duration=5.0)
        assert root._layer_stack.top(LayerKind.TOAST) is toast1

        toast2 = root.show_toast("second", duration=5.0)
        # 旧 Toast 应该被移除
        assert root._layer_stack.top(LayerKind.TOAST) is toast2
        assert toast1.open is False  # 旧 Toast 被关闭

    def test_show_sheet(self):
        from pigit.termui._component_base import Component

        class _Inner(Component):
            NAME = "inner"

            def _render_surface(self, surface):
                pass

            def refresh(self):
                pass

        inner = _Inner()
        root = ComponentRoot(DummyBody())
        root.resize((80, 24))
        sheet = root.show_sheet(inner, height=6)
        assert root._layer_stack.top(LayerKind.SHEET) is sheet
        assert sheet._child is inner
        assert inner.parent is sheet

    def test_toast_expires_on_render(self):
        root = ComponentRoot(DummyBody())
        toast = root.show_toast("expiring", duration=0.0)
        assert root._layer_stack.top(LayerKind.TOAST) is toast
        from pigit.termui._surface import Surface

        surface = Surface(10, 5)
        root._render_surface(surface)
        assert root._layer_stack.top(LayerKind.TOAST) is None
        assert toast.open is False

    def test_toast_clock_injection(self):
        from pigit.termui._overlay_components import Toast

        clock_calls = [0.0, 2.0, 10.0]
        idx = 0

        def fake_clock():
            nonlocal idx
            val = clock_calls[idx]
            idx += 1
            return val

        toast = Toast("injected", duration=5.0, clock=fake_clock)
        assert not toast.is_expired()  # 2.0 - 0.0 = 2.0 <= 5.0
        assert toast.is_expired()  # 10.0 - 0.0 = 10.0 > 5.0

    # --- Badge ---

    def test_badge_starts_none(self):
        root = ComponentRoot(DummyBody())
        assert root.badge_text is None

    def test_show_badge_sets_text(self):
        root = ComponentRoot(DummyBody())
        root.show_badge("3 staged")
        assert root.badge_text == "3 staged"

    def test_hide_badge_clears_text(self):
        root = ComponentRoot(DummyBody())
        root.show_badge("3 staged")
        root.hide_badge()
        assert root.badge_text is None

    def test_show_badge_overwrites_previous(self):
        root = ComponentRoot(DummyBody())
        root.show_badge("old")
        root.show_badge("new")
        assert root.badge_text == "new"

    def test_destroy_resets_overlay_host(self):
        """destroy() cleans up the overlay host ContextVar without error."""
        root = ComponentRoot(DummyBody())
        root.destroy()  # should not raise
