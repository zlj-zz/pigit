# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_runtime_context.py
Description: Tests for RuntimeContext unified facade.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

import pytest

from pigit.termui._runtime_context import (
    RuntimeContext,
    _runtime_ctx,
    ComponentRegistry,
    get_session,
    get_renderer,
    get_overlay_host,
    get_registry,
    get_focus_manager,
    get_render_request,
    set_session,
    set_renderer,
    set_overlay_host,
    set_registry,
    set_focus_manager,
    set_render_request,
    reset_session,
    reset_renderer,
    reset_overlay_host,
    reset_registry,
    reset_focus_manager,
    reset_render_request,
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


class DummySession:
    pass


class DummyRenderer:
    pass


class DummyHost:
    pass


class TestRuntimeContextCurrent:
    """RuntimeContext.current() reads from the single _runtime_ctx."""

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
    """RuntimeContext is a mutable container for runtime subsystems."""

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
    """set_* / get_* helpers read and write through _runtime_ctx."""

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
    """reset_* helpers clear fields on the active RuntimeContext."""

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
        from unittest.mock import MagicMock
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
    """request_render() forwards to the callback stored in RuntimeContext."""

    def test_request_render_calls_callback(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        called = [False]

        def cb():
            called[0] = True

        set_render_request(cb)
        from pigit.termui._runtime_context import request_render

        request_render()
        assert called[0]

    def test_request_render_noop_when_no_callback(self):
        runtime = RuntimeContext()
        _runtime_ctx.set(runtime)
        from pigit.termui._runtime_context import request_render

        request_render()  # should not raise
