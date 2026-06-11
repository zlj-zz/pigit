# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_runtime_context.py
Description: Tests for RuntimeContext unified facade.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from pigit.termui._component import Component
from pigit.termui._layer import LayerKind
from pigit.termui._root import ComponentRoot
from pigit.termui._runtime_context import (
    ComponentRegistry,
    RuntimeContext,
    RendererNotBoundError,
    _runtime_ctx,
    by_id,
    get_focus_manager,
    get_overlay_host,
    get_registry,
    get_renderer,
    get_renderer_strict,
    get_render_request,
    get_session,
    is_modal_open,
    layer_pop,
    layer_push,
    layer_top,
    request_render,
    reset_focus_manager,
    reset_overlay_host,
    reset_registry,
    reset_render_request,
    reset_renderer,
    reset_session,
    set_focus_manager,
    set_overlay_host,
    set_registry,
    set_render_request,
    set_renderer,
    set_session,
)


@pytest.fixture(autouse=True)
def _clear_runtime_context():
    """Reset _runtime_ctx to default before each test."""
    token = _runtime_ctx.set(None)
    yield
    try:
        _runtime_ctx.reset(token)
    except Exception:
        pass


class _Leaf(Component):
    NAME = "leaf"

    def _render_surface(self, surface):
        pass


class DummySession:
    pass


class DummyRenderer:
    pass


class DummyHost:
    pass


class TestRuntimeContextCurrent:
    def test_current_returns_none_when_no_context_set(self):
        assert RuntimeContext.current() is None

    def test_current_returns_runtime_when_set(self):
        runtime = RuntimeContext()
        token = _runtime_ctx.set(runtime)
        try:
            assert RuntimeContext.current() is runtime
        finally:
            _runtime_ctx.reset(token)


class TestRuntimeContextFields:
    def test_fields_default_to_none(self):
        runtime = RuntimeContext()
        assert runtime.session is None
        assert runtime.renderer is None
        assert runtime.overlay_host is None
        assert runtime.focus_manager is None
        assert runtime.render_request is None

    def test_registry_defaults_to_instance(self):
        runtime = RuntimeContext()
        assert isinstance(runtime.registry, ComponentRegistry)

    def test_fields_are_mutable(self):
        runtime = RuntimeContext()
        session = DummySession()
        runtime.session = session
        assert runtime.session is session


class TestSetGetHelpers:
    def test_set_get_session(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        session = DummySession()
        set_session(session)
        assert get_session() is session

    def test_set_get_renderer(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        renderer = DummyRenderer()
        set_renderer(renderer)
        assert get_renderer() is renderer

    def test_set_get_overlay_host(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = DummyHost()
        set_overlay_host(host)
        assert get_overlay_host() is host

    def test_set_get_registry(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        reg = ComponentRegistry()
        set_registry(reg)
        assert get_registry() is reg

    def test_set_get_render_request(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        cb = lambda: None
        set_render_request(cb)
        assert get_render_request() is cb

    def test_get_returns_none_when_no_runtime(self):
        assert get_session() is None
        assert get_renderer() is None
        assert get_overlay_host() is None
        assert get_registry() is None
        assert get_focus_manager() is None
        assert get_render_request() is None


class TestResetHelpers:
    def test_reset_session(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        set_session(DummySession())
        reset_session()
        assert get_session() is None

    def test_reset_renderer(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        set_renderer(DummyRenderer())
        reset_renderer()
        assert get_renderer() is None

    def test_reset_overlay_host(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        set_overlay_host(DummyHost())
        reset_overlay_host()
        assert get_overlay_host() is None

    def test_reset_registry(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        set_registry(ComponentRegistry())
        reset_registry()
        assert get_registry() is None

    def test_reset_focus_manager(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        from pigit.termui._runtime_context import FocusManager

        set_focus_manager(FocusManager(MagicMock()))
        reset_focus_manager()
        assert get_focus_manager() is None

    def test_reset_render_request(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        set_render_request(lambda: None)
        reset_render_request()
        assert get_render_request() is None


class TestRequestRender:
    def test_request_render_calls_callback(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        called = [False]

        def cb():
            called[0] = True

        set_render_request(cb)
        request_render()
        assert called[0]

    def test_request_render_noop_when_no_callback(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        request_render()


class TestComponentRegistry:
    def test_register_and_by_id(self):
        reg = ComponentRegistry()
        comp = MagicMock()
        comp.id = "foo"
        reg.register(comp)
        assert reg.by_id("foo") is comp

    def test_by_id_returns_none_when_not_found(self):
        reg = ComponentRegistry()
        assert reg.by_id("missing") is None

    def test_unregister(self):
        reg = ComponentRegistry()
        comp = MagicMock()
        comp.id = "foo"
        reg.register(comp)
        reg.unregister(comp)
        assert reg.by_id("foo") is None

    def test_register_skips_when_no_id(self):
        reg = ComponentRegistry()
        comp = MagicMock()
        comp.id = ""
        reg.register(comp)
        assert reg.by_id("") is None

    def test_unregister_skips_when_no_id(self):
        reg = ComponentRegistry()
        comp = MagicMock()
        comp.id = ""
        reg.unregister(comp)

    def test_duplicate_id_logs_warning(self, caplog):
        reg = ComponentRegistry()
        a = MagicMock()
        a.id = "dup"
        b = MagicMock()
        b.id = "dup"
        reg.register(a)
        with caplog.at_level("WARNING"):
            reg.register(b)
        assert "Duplicate component id" in caplog.text


class TestById:
    def test_found(self):
        from pigit.termui._component import Component

        class _C(Component):
            NAME = "c"

            def _render_surface(self, surface):
                pass

        c = _C()
        c.id = "x"
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        set_registry(runtime.registry)
        runtime.registry.register(c)
        assert by_id("x") is c

    def test_not_found_raises(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        with pytest.raises(RuntimeError, match="Component 'nope' not found"):
            by_id("nope")

    def test_type_mismatch_raises(self):
        from pigit.termui._component import Component

        class _A(Component):
            NAME = "a"

            def _render_surface(self, surface):
                pass

        a = _A()
        a.id = "a"
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        set_registry(runtime.registry)
        runtime.registry.register(a)
        with pytest.raises(TypeError, match="expected str"):
            by_id("a", expect_type=str)

    def test_no_runtime_raises(self):
        with pytest.raises(RuntimeError, match="Component 'x' not found"):
            by_id("x")


class TestRendererNotBoundError:
    def test_message(self):
        with pytest.raises(RendererNotBoundError, match="Renderer not bound"):
            raise RendererNotBoundError()


class TestGetRendererStrict:
    def test_returns_renderer_when_set(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        renderer = MagicMock()
        set_renderer(renderer)
        assert get_renderer_strict() is renderer

    def test_raises_when_not_set(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        with pytest.raises(RendererNotBoundError):
            get_renderer_strict()


class TestLayerHelpers:
    def test_layer_push(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = MagicMock()
        host._layer_stack = MagicMock()
        set_overlay_host(host)
        comp = MagicMock()
        layer_push(LayerKind.MODAL, comp)
        host._layer_stack.push.assert_called_once_with(LayerKind.MODAL, comp)

    def test_layer_pop(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = MagicMock()
        host._layer_stack = MagicMock()
        host._layer_stack.pop.return_value = MagicMock()
        set_overlay_host(host)
        result = layer_pop(LayerKind.MODAL)
        assert result is host._layer_stack.pop.return_value

    def test_layer_pop_no_host(self):
        assert layer_pop(LayerKind.MODAL) is None

    def test_layer_top(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = MagicMock()
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = MagicMock()
        set_overlay_host(host)
        assert layer_top(LayerKind.MODAL) is host._layer_stack.top.return_value

    def test_is_modal_open_true(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = MagicMock()
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = MagicMock()
        set_overlay_host(host)
        assert is_modal_open() is True

    def test_is_modal_open_false(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        host = MagicMock()
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = None
        set_overlay_host(host)
        assert is_modal_open() is False


class TestFocusManagerPolicy:
    def test_sync_focus_to_overlay_or_leaf_with_overlay(self):
        body = _Leaf()
        root = ComponentRoot(body)
        overlay = _Leaf()
        overlay.open = True
        root._layer_stack.push(LayerKind.MODAL, overlay)
        fm = root._focus_manager
        fm.sync_focus_to_overlay_or_leaf()
        assert fm.get_focus_leaf() is overlay

    def test_sync_focus_to_overlay_or_leaf_without_overlay(self):
        body = _Leaf()
        root = ComponentRoot(body)
        fm = root._focus_manager
        fm.sync_focus_to_overlay_or_leaf()
        assert fm.get_focus_leaf() is body

    def test_sync_focus_to_overlay_does_nothing_when_no_overlay(self):
        body = _Leaf()
        root = ComponentRoot(body)
        fm = root._focus_manager
        fm.set_focus_chain(body)
        fm.sync_focus_to_overlay()
        assert fm.get_focus_leaf() is body

    def test_sync_focus_if_overlay_closed_restores_focus(self):
        body = _Leaf()
        root = ComponentRoot(body)
        overlay = _Leaf()
        root._layer_stack.push(LayerKind.MODAL, overlay)
        fm = root._focus_manager
        fm.set_focus_chain(overlay)
        root._layer_stack.pop(LayerKind.MODAL)
        fm.sync_focus_if_overlay_closed(was_open=True, now_open=False)
        assert fm.get_focus_leaf() is body

    def test_sync_focus_if_overlay_closed_no_op_when_still_open(self):
        body = _Leaf()
        root = ComponentRoot(body)
        overlay = _Leaf()
        root._layer_stack.push(LayerKind.MODAL, overlay)
        fm = root._focus_manager
        fm.set_focus_chain(overlay)
        fm.sync_focus_if_overlay_closed(was_open=True, now_open=True)
        assert fm.get_focus_leaf() is overlay

    def test_get_event_target_returns_leaf(self):
        body = _Leaf()
        root = ComponentRoot(body)
        fm = root._focus_manager
        assert fm.get_event_target() is body


class TestFocusManagerMechanics:
    def test_focus_grab_and_release(self):
        body = _Leaf()
        root = ComponentRoot(body)
        fm = root._focus_manager
        other = _Leaf()
        fm.focus_grab(other)
        assert fm.get_focus_leaf() is other
        fm.focus_release()
        assert fm.get_focus_leaf() is body

    def test_focus_release_to_none(self):
        body = _Leaf()
        root = ComponentRoot(body)
        fm = root._focus_manager
        fm.clear_focus()
        other = _Leaf()
        fm.focus_grab(other)
        fm.focus_release()
        assert fm.get_focus_leaf() is None

    def test_focus_grab_stack_overflow(self, caplog):
        body = _Leaf()
        root = ComponentRoot(body)
        fm = root._focus_manager
        for i in range(10):
            fm.focus_grab(_Leaf())
        assert len(fm._focus_stack) == 8
        assert "overflow" in caplog.text

    def test_clear_focus(self):
        body = _Leaf()
        root = ComponentRoot(body)
        fm = root._focus_manager
        fm.set_focus_chain(body)
        assert body._focus_level == 0
        fm.clear_focus()
        assert fm.get_focus_leaf() is None
        assert body._focus_level == -1

    def test_set_focus_chain_noop_when_same_leaf(self):
        body = _Leaf()
        root = ComponentRoot(body)
        fm = root._focus_manager
        fm.set_focus_chain(body)
        fm.set_focus_chain(body)
        assert fm.get_focus_leaf() is body
