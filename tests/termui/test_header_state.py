"""
Tests for HeaderState event-driven updates.
"""

from __future__ import annotations

import pytest

from pigit.app_header_state import HeaderState
from pigit.app_theme import THEME
from pigit.termui import EventType, EVT_SELECTION_CHANGED
from pigit.termui.event_bus import EventBus


@pytest.fixture
def header_state() -> HeaderState:
    return HeaderState(THEME)


@pytest.fixture
def tab_config() -> dict[type, tuple[str, str]]:
    return {int: ("Fallback", "9")}


def test_bind_to_bus_updates_mode(header_state: HeaderState) -> None:
    bus = EventBus()
    header_state.bind_to_bus(bus, {})

    bus.publish(EventType("mode_changed"), mode="visual")

    assert header_state.mode == "visual"


def test_bind_to_bus_updates_tab_from_active_metadata(
    header_state: HeaderState,
) -> None:
    bus = EventBus()
    header_state.bind_to_bus(bus, {})

    active = type("Active", (), {"tab_name": "Status", "tab_key": "1"})()
    bus.publish(EVT_SELECTION_CHANGED, active=active)

    assert header_state.tab == "Status"
    assert header_state.tab_key == "1"


def test_bind_to_bus_falls_back_to_tab_config(
    header_state: HeaderState, tab_config: dict[type, tuple[str, str]]
) -> None:
    bus = EventBus()
    header_state.bind_to_bus(bus, tab_config)

    active = 42
    bus.publish(EVT_SELECTION_CHANGED, active=active)

    assert header_state.tab == "Fallback"
    assert header_state.tab_key == "9"


def test_bind_to_bus_unsubscribe_stops_updates(
    header_state: HeaderState,
) -> None:
    bus = EventBus()
    unsub = header_state.bind_to_bus(bus, {})

    bus.publish(EventType("mode_changed"), mode="visual")
    assert header_state.mode == "visual"

    unsub()
    bus.publish(EventType("mode_changed"), mode="normal")
    assert header_state.mode == "visual"
