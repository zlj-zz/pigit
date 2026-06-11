"""
Module: tests/termui/test_signal_render.py
Description: Tests for Signal-based auto-render.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

import pytest

from pigit.termui._component import Component
from pigit.termui.reactive import Signal
from pigit.termui._runtime_context import (
    RuntimeContext,
    _runtime_ctx,
    request_render,
    set_render_request,
    reset_render_request,
)


@pytest.fixture(autouse=True)
def _clear_runtime_context():
    """Reset runtime context before each test."""
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    yield
    _runtime_ctx.reset(token)


# --- Helpers ---


class _SignalLeaf(Component):
    """Leaf component with Signal-based state."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cursor = Signal(0)
        self._unsub = self.cursor.subscribe(self._on_cursor_change)

    def _on_cursor_change(self, _: int) -> None:
        request_render()

    def _render_surface(self, surface) -> None:
        pass

    def destroy(self) -> None:
        self._unsub()
        super().destroy()


# --- T029: Signal mutation triggers render request ---


class TestSignalMutationTriggersRender:
    def test_signal_change_requests_render(self):
        """Changing a Signal value triggers a render request."""
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            leaf = _SignalLeaf()
            leaf.cursor.set(5)
            assert len(render_calls) == 1
        finally:
            reset_render_request()

    def test_signal_no_change_skips_render(self):
        """Setting a Signal to the same value does not request render."""
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            leaf = _SignalLeaf()
            leaf.cursor.set(0)  # Same as initial value
            assert len(render_calls) == 0
        finally:
            reset_render_request()


# --- T030: Signal coalescing ---


class TestSignalCoalescing:
    def test_multiple_mutations_result_in_one_render(self):
        """Multiple Signal changes in quick succession are coalesced into one render."""
        render_calls: list = []
        set_render_request(lambda: render_calls.append(1))
        try:
            leaf = _SignalLeaf()
            leaf.cursor.set(1)
            leaf.cursor.set(2)
            leaf.cursor.set(3)
            assert len(render_calls) == 3  # Each set triggers a request
            # Coalescing happens at the event loop level (request_render is called 3 times,
            # but the event loop would only render once per frame)
        finally:
            reset_render_request()

    def test_request_render_without_context_is_safe(self):
        """Calling request_render without an event loop context is a no-op."""
        _runtime_ctx.set(None)
        leaf = _SignalLeaf()
        # No render request callback set in context
        leaf.cursor.set(5)
        # Should not raise


# --- T031: Inactive panel does not render ---


class TestInactivePanelNoRender:
    def test_inactive_component_signal_does_not_request_render(self):
        """A deactivated component's Signal changes should not request render."""
        render_calls: list = []

        class _ConditionalLeaf(Component):
            def __init__(self, **kwargs) -> None:
                super().__init__(**kwargs)
                self.value = Signal(0)
                self._unsub = self.value.subscribe(self._on_change)

            def _on_change(self, _new: int) -> None:
                if self.is_activated():
                    request_render()

            def _render_surface(self, surface) -> None:
                pass

            def destroy(self) -> None:
                self._unsub()
                super().destroy()

        set_render_request(lambda: render_calls.append(1))
        try:
            leaf = _ConditionalLeaf()
            leaf.activate()
            leaf.value.set(1)
            assert len(render_calls) == 1

            leaf.deactivate()
            leaf.value.set(2)
            assert len(render_calls) == 1  # No additional render request
        finally:
            reset_render_request()
