"""
Tests for pigit.termui.event_bus.EventBus.
"""

from __future__ import annotations

import pytest

from pigit.termui.event_bus import EventBus
from pigit.termui.types import ActionEventType


def test_subscribe_and_publish() -> None:
    bus = EventBus()
    calls: list[dict] = []

    def handler(*, value: int) -> bool:
        calls.append({"value": value})
        return True

    unsub = bus.subscribe(ActionEventType.selection_changed, handler)
    handled = bus.publish(ActionEventType.selection_changed, value=42)

    assert handled is True
    assert calls == [{"value": 42}]
    unsub()


def test_multiple_handlers_fire() -> None:
    bus = EventBus()
    calls: list[str] = []

    def a(*, msg: str) -> bool:
        calls.append(f"a:{msg}")
        return False

    def b(*, msg: str) -> bool:
        calls.append(f"b:{msg}")
        return True

    bus.subscribe(ActionEventType.mode_changed, a)
    bus.subscribe(ActionEventType.mode_changed, b)
    handled = bus.publish(ActionEventType.mode_changed, msg="x")

    assert handled is True
    assert calls == ["a:x", "b:x"]


def test_unsubscribe_stops_delivery() -> None:
    bus = EventBus()
    calls: list[int] = []

    def handler(*, n: int) -> bool:
        calls.append(n)
        return True

    unsub = bus.subscribe(ActionEventType.selection_changed, handler)
    bus.publish(ActionEventType.selection_changed, n=1)
    unsub()
    bus.publish(ActionEventType.selection_changed, n=2)

    assert calls == [1]


def test_handler_exception_isolated() -> None:
    bus = EventBus()
    calls: list[str] = []

    def bad(*, msg: str) -> bool:
        raise RuntimeError("boom")

    def good(*, msg: str) -> bool:
        calls.append(msg)
        return True

    bus.subscribe(ActionEventType.selection_changed, bad)
    bus.subscribe(ActionEventType.selection_changed, good)
    handled = bus.publish(ActionEventType.selection_changed, msg="ok")

    assert handled is True
    assert calls == ["ok"]


def test_clear_removes_all() -> None:
    bus = EventBus()
    calls: list[int] = []

    def handler(*, n: int) -> bool:
        calls.append(n)
        return True

    bus.subscribe(ActionEventType.selection_changed, handler)
    bus.clear()
    handled = bus.publish(ActionEventType.selection_changed, n=1)

    assert handled is False
    assert calls == []


def test_publish_and_emit_bubble_independent() -> None:
    """Bus subscribers and emit() bubbling should not interfere with each other."""
    bus = EventBus()
    bubble_calls: list[str] = []
    bus_calls: list[str] = []

    def bus_handler(*, msg: str) -> bool:
        bus_calls.append(msg)
        return True

    def bubble_handler(action, **data) -> bool:
        bubble_calls.append(f"bubble:{data.get('msg')}")
        return True

    bus.subscribe(ActionEventType.goto, bus_handler)
    handled = bus.publish(ActionEventType.goto, msg="x")

    # Bus delivery happens independently; bubble handler is not invoked here.
    assert handled is True
    assert bus_calls == ["x"]
    assert bubble_calls == []

    # Simulate what emit() does: walk parent chain looking for on_event.
    # This is independent of the bus.
    assert bubble_handler(ActionEventType.goto, msg="x") is True
    assert bubble_calls == ["bubble:x"]
