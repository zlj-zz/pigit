"""
Tests for PigitApplication event routing via the framework EventBus.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from pigit.termui import ActionEventType
from pigit.termui.event_bus import EventBus


class _FakeApp:
    """Minimal stand-in for the Application-level wiring we need to test."""

    def __init__(self) -> None:
        self._event_bus = EventBus()
        self.merge_calls: list[tuple[str, str]] = []

    def _on_merge_request(self, source: str, target: str) -> None:
        self.merge_calls.append((source, target))

    def on_event(self, action: ActionEventType, **data) -> bool:
        handled = self._event_bus.publish(action, **data)
        if action is ActionEventType.action_requested and data.get("cmd") == "merge":
            self._on_merge_request(data["source"], data["target"])
            return True
        return handled


def test_on_event_publishes_selection_changed_to_bus() -> None:
    app = _FakeApp()
    calls: list[str] = []

    def subscriber(*, active: object | None = None, **_) -> bool:
        calls.append("sub")
        return True

    app._event_bus.subscribe(ActionEventType.selection_changed, subscriber)
    result = app.on_event(ActionEventType.selection_changed, active=Mock())

    assert result is True
    assert calls == ["sub"]


def test_on_event_publishes_mode_changed_to_bus() -> None:
    app = _FakeApp()
    calls: list[str] = []

    def subscriber(*, mode: str, **_) -> bool:
        calls.append(mode)
        return True

    app._event_bus.subscribe(ActionEventType.mode_changed, subscriber)
    result = app.on_event(ActionEventType.mode_changed, mode="visual")

    assert result is True
    assert calls == ["visual"]


def test_merge_request_routes_to_on_merge_request() -> None:
    app = _FakeApp()
    result = app.on_event(
        ActionEventType.action_requested,
        cmd="merge",
        source="feature",
        target="main",
    )

    assert result is True
    assert app.merge_calls == [("feature", "main")]


def test_goto_returns_false_when_no_subscriber() -> None:
    app = _FakeApp()
    result = app.on_event(ActionEventType.goto, target="status")

    assert result is False


def test_bus_subscriber_exception_does_not_crash_on_event() -> None:
    app = _FakeApp()

    def bad(**_) -> bool:
        raise RuntimeError("boom")

    app._event_bus.subscribe(ActionEventType.selection_changed, bad)
    # Should not raise despite bad handler
    result = app.on_event(ActionEventType.selection_changed, active=Mock())

    # No subscriber returned True, so handled is False
    assert result is False
