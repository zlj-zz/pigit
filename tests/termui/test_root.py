# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_root.py
Description: Tests for pigit.termui.root.
Author: Zev
Date: 2026-04-17
"""

import pytest
from unittest.mock import MagicMock

from pigit.termui._component import Component
from pigit.termui import ToastPosition
from pigit.termui._layer import LayerKind
from pigit.termui._root import ComponentRoot
from pigit.termui.types import OverlayDispatchResult, EVT_GOTO
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx


@pytest.fixture(autouse=True)
def _runtime_context():
    """Provide a fresh RuntimeContext for root tests."""
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    yield
    _runtime_ctx.reset(token)


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

        class _ModalPopup(Component):
            open = True

            def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
                return OverlayDispatchResult.HANDLED_EXPLICIT

            def _render_surface(self, surface) -> None:
                pass

        popup = _ModalPopup()
        root._layer_stack.push(LayerKind.MODAL, popup)
        root._handle_event("k")
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

        root.body.accept = MagicMock()
        root.accept(EVT_GOTO, target="x")
        root.body.accept.assert_called_once_with(EVT_GOTO, target="x")

    def test_fresh_does_not_raise(self):
        root = ComponentRoot(DummyBody())
        root.refresh()

    def test_show_toast(self):
        from pigit.termui._runtime_context import set_overlay_host
        from pigit.termui._overlay_api import show_toast

        root = ComponentRoot(DummyBody())
        root.resize((80, 24))
        set_overlay_host(root)
        toast = show_toast("hello", duration=1.5)
        assert toast is not None
        assert root._layer_stack.top(LayerKind.TOAST) is toast
        assert len(toast._segments) == 1
        assert toast._segments[0].text == "hello"
        assert toast.duration == 1.5

    def test_show_toast_with_position(self):
        """验证 show_toast 支持 position 参数"""
        from pigit.termui._runtime_context import set_overlay_host
        from pigit.termui._overlay_api import show_toast

        root = ComponentRoot(DummyBody())
        root.resize((80, 24))
        set_overlay_host(root)
        toast = show_toast("hello", duration=1.5, position=ToastPosition.BOTTOM_LEFT)
        assert toast is not None
        assert toast._position == ToastPosition.BOTTOM_LEFT

    def test_show_toast_singleton_replaces_existing(self):
        """验证新 Toast 替换旧 Toast（单例模式）"""
        from pigit.termui._runtime_context import set_overlay_host
        from pigit.termui._overlay_api import show_toast

        root = ComponentRoot(DummyBody())
        root.resize((80, 24))
        set_overlay_host(root)
        toast1 = show_toast("first", duration=5.0)
        assert toast1 is not None
        assert root._layer_stack.top(LayerKind.TOAST) is toast1

        toast2 = show_toast("second", duration=5.0)
        assert toast2 is not None
        # 旧 Toast 应该被移除
        assert root._layer_stack.top(LayerKind.TOAST) is toast2
        assert toast1.open is False  # 旧 Toast 被关闭

    def test_show_sheet(self):
        from pigit.termui._component import Component

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

    def test_sheet_mouse_miss_falls_through_to_body(self):
        from pigit.termui._mouse import MouseButton, MouseEvent, MouseKind

        hits: list[tuple[int, int]] = []

        class _Body(DummyBody):
            def handle_mouse(self, event):
                hits.append((event.col, event.row))
                return True

            def _hit_test(self, col, row):
                return self, col, row

        class _Inner(Component):
            NAME = "inner"

            def _render_surface(self, surface):
                pass

            def refresh(self):
                pass

        body = _Body()
        root = ComponentRoot(body)
        root.resize((80, 24))
        root.show_sheet(_Inner(), height=4, edge="top")
        ev = MouseEvent(col=10, row=20, button=MouseButton.LEFT, kind=MouseKind.PRESS)
        # The top-edge sheet covers rows 1..4; a click at row 20 is outside it
        # and must reach the body instead of being swallowed.
        assert root._handle_mouse(ev) is True
        assert hits == [(10, 20)]

    def test_sheet_mouse_hit_does_not_reach_body(self):
        from pigit.termui._mouse import MouseButton, MouseEvent, MouseKind

        hits: list[tuple[int, int]] = []

        class _Body(DummyBody):
            def handle_mouse(self, event):
                hits.append((event.col, event.row))
                return True

            def _hit_test(self, col, row):
                return self, col, row

        class _Inner(Component):
            NAME = "inner"

            def _render_surface(self, surface):
                pass

            def refresh(self):
                pass

        body = _Body()
        root = ComponentRoot(body)
        root.resize((80, 24))
        root.show_sheet(_Inner(), height=4, edge="top")
        ev = MouseEvent(col=10, row=2, button=MouseButton.LEFT, kind=MouseKind.PRESS)
        assert root._handle_mouse(ev) is True
        assert hits == []

    def test_toast_expires_on_render(self):
        from pigit.termui._runtime_context import (
            set_overlay_host,
            reset_overlay_host,
        )
        from pigit.termui._overlay_api import show_toast

        root = ComponentRoot(DummyBody())
        set_overlay_host(root)
        try:
            toast = show_toast("expiring", duration=0.0)
            assert toast is not None
            assert root._layer_stack.top(LayerKind.TOAST) is toast
            from pigit.termui._surface import Surface

            surface = Surface(10, 5)
            root._render_surface(surface)
            assert root._layer_stack.top(LayerKind.TOAST) is None
            assert toast.open is False
        finally:
            reset_overlay_host()

    def test_toast_clock_injection(self):
        from pigit.termui.widgets import Toast

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


class _DroppingOverlay(Component):
    """Modal that is open but does not consume keys."""

    def __init__(self) -> None:
        super().__init__()
        self.open = True

    def _render_surface(self, surface) -> None:
        pass

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        return OverlayDispatchResult.DROPPED_UNBOUND


class _ConsumingOverlay(Component):
    """Modal that consumes every key."""

    def __init__(self) -> None:
        super().__init__()
        self.open = True
        self.received: list[str] = []

    def _render_surface(self, surface) -> None:
        pass

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        self.received.append(key)
        return OverlayDispatchResult.HANDLED_EXPLICIT


class _RecordingBody(Component):
    """Body that records keys reaching handle_key."""

    NAME = "recording"

    def __init__(self) -> None:
        super().__init__()
        self.received: list[str] = []

    def _render_surface(self, surface) -> None:
        pass

    def handle_key(self, key: str) -> bool:
        self.received.append(key)
        return True


class TestComponentRootKeyDispatch:
    def test_root_binding_closes_overlay_restores_focus(self):
        body = DummyBody()
        root = ComponentRoot(
            body,
            key_handlers={"x": lambda: root._layer_stack.pop(LayerKind.MODAL)},
        )
        overlay = _DroppingOverlay()
        root._layer_stack.push(LayerKind.MODAL, overlay)
        root._focus_manager.set_focus_chain(overlay)

        assert root._handle_event("x") is True
        assert body.is_focus_leaf

    def test_root_handle_key_is_fallback_after_tree(self):
        """Root handle_key fires only for keys the focus leaf declined."""

        class _SelectiveBody(Component):
            def _render_surface(self, surface) -> None:
                pass

            def handle_key(self, key: str) -> bool:
                return key != "j"  # declines "j", consumes everything else

        seen: list[str] = []
        root = ComponentRoot(
            _SelectiveBody(),
            handle_key=lambda key: seen.append(key) or True,
        )

        # "j" declined by the tree → root handle_key fires.
        assert root._handle_event("j") is True
        assert seen == ["j"]

        # "k" consumed by the tree → root handle_key does not fire.
        assert root._handle_event("k") is True
        assert seen == ["j"]

    def test_root_binding_precedes_handle_key(self):
        body = DummyBody()
        bound_called = []
        handle_called = []

        root = ComponentRoot(
            body,
            key_handlers={"x": lambda: bound_called.append(True)},
            handle_key=lambda key: handle_called.append(key) or True,
        )

        assert root._handle_event("x") is True
        assert bound_called == [True]
        assert handle_called == []

    def test_overlay_consumes_before_root_binding(self):
        body = DummyBody()
        bound_called = []
        overlay = _ConsumingOverlay()
        root = ComponentRoot(
            body,
            key_handlers={"x": lambda: bound_called.append(True)},
        )
        root._layer_stack.push(LayerKind.MODAL, overlay)

        assert root._handle_event("x") is True
        assert overlay.received == ["x"]
        assert bound_called == []

    def test_overlay_drop_falls_through_to_root_binding(self):
        body = DummyBody()
        bound_called = []
        root = ComponentRoot(
            body,
            key_handlers={"x": lambda: bound_called.append(True)},
        )
        root._layer_stack.push(LayerKind.MODAL, _DroppingOverlay())

        assert root._handle_event("x") is True
        assert bound_called == [True]

    def test_root_binding_runs_once_as_fallback(self):
        """A declined leaf bubbles and the root binding fires exactly once."""
        hits: list[str] = []

        class _BubblingBody(Component):
            def _render_surface(self, surface) -> None:
                pass

            def handle_key(self, key: str) -> bool:
                hits.append("body")
                return False

        body = _BubblingBody()
        root = ComponentRoot(
            body,
            key_handlers={"z": lambda: hits.append("root")},
        )

        # Leaf declines "z", bubbles, then the root binding fires once.
        assert root._handle_event("z") is True
        assert hits == ["body", "root"]

        hits.clear()
        assert root._handle_event("q") is False
        assert hits == ["body"]
