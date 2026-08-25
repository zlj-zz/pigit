"""
Module: tests/termui/test_event_bubble.py
Description: Tests for event bubbling between components.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pigit.termui.component import Component
from pigit.termui.containers import TabView
from pigit.termui.types import EventType, EVT_GOTO, EVT_SELECTION_CHANGED

# --- Helpers ---


class _EventLeaf(Component):
    """Leaf component that can emit events."""

    def __init__(self, label: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.label = label

    def update(self, action, **data) -> None:
        pass

    def paint(self, surface) -> None:
        pass


class _EventTabView(TabView):
    def update(self, action: EventType, **data) -> None:
        pass


# --- T020: emit reaches Application handler ---


class TestEmitReachesApplication:
    def test_emit_bubbles_to_parent_on_event(self):
        """An emitted action bubbles up to the first parent with on_event."""
        parent = _EventLeaf("parent")
        child = _EventLeaf("child")
        child.parent = parent
        parent.on_event = MagicMock(return_value=True)

        child.emit(EVT_GOTO, target="x")

        parent.on_event.assert_called_once_with(EVT_GOTO, target="x")

    def test_emit_bubbles_through_multiple_parents(self):
        """An emitted action bubbles through intermediate parents to the root."""
        grandparent = _EventLeaf("grandparent")
        parent = _EventLeaf("parent")
        child = _EventLeaf("child")
        child.parent = parent
        parent.parent = grandparent

        grandparent.on_event = MagicMock(return_value=True)

        child.emit(EVT_SELECTION_CHANGED, index=5)

        grandparent.on_event.assert_called_once_with(EVT_SELECTION_CHANGED, index=5)

    def test_emit_stops_at_first_handler(self):
        """Event bubbling stops at the first ancestor whose on_event returns True."""
        grandparent = _EventLeaf("grandparent")
        parent = _EventLeaf("parent")
        child = _EventLeaf("child")
        child.parent = parent
        parent.parent = grandparent

        parent.on_event = MagicMock(return_value=True)
        grandparent.on_event = MagicMock(return_value=True)

        child.emit(EVT_GOTO, target="x")

        parent.on_event.assert_called_once()
        grandparent.on_event.assert_not_called()


# --- T021: source identification in event payload ---


class TestSourceIdentification:
    def test_emit_includes_source_in_payload(self):
        """Events should include source component for handler differentiation."""
        parent = _EventLeaf("parent")
        child = _EventLeaf("child", id="child_id")
        child.parent = parent
        parent.on_event = MagicMock(return_value=True)

        child.emit(EventType("action_requested"), cmd="test", source=child)

        call_args = parent.on_event.call_args
        assert call_args.kwargs["source"] is child
        assert call_args.kwargs["cmd"] == "test"

    def test_source_helps_differentiate_same_action(self):
        """Application can distinguish same action from different panels via source."""
        app = _EventLeaf("app", id="app")
        panel_a = _EventLeaf("panel_a", id="panel_a")
        panel_b = _EventLeaf("panel_b", id="panel_b")
        panel_a.parent = app
        panel_b.parent = app

        received: list = []

        def on_event(action, **data):
            received.append((data.get("source"), action))
            return True

        app.on_event = on_event

        panel_a.emit(EVT_SELECTION_CHANGED, source=panel_a, index=1)
        panel_b.emit(EVT_SELECTION_CHANGED, source=panel_b, index=2)

        assert received == [
            (panel_a, EVT_SELECTION_CHANGED),
            (panel_b, EVT_SELECTION_CHANGED),
        ]


# --- T022: goto routing via TabView.on_event ---


class TestGotoRouting:
    def test_tab_view_handles_goto_action(self):
        """TabView accepts goto action and routes to the target child."""
        main = _EventLeaf("main", id="main")
        secondary = _EventLeaf("secondary", id="secondary")
        tab_view = _EventTabView(children=[main, secondary], start="main")

        assert tab_view.visible is main

        tab_view.accept(EVT_GOTO, target="secondary")

        assert tab_view.visible is secondary

    def test_goto_accept_switches_tabs(self):
        """TabView switches tabs via accept/route_to, not on_event bubble."""
        main = _EventLeaf("main", id="main")
        secondary = _EventLeaf("secondary", id="secondary")
        tab_view = _EventTabView(children=[main, secondary], start="main")

        main.emit(EVT_GOTO, target="secondary")
        assert tab_view.visible is main  # EVT_GOTO is not consumed by TabView

        tab_view.accept(EVT_GOTO, target="secondary")
        assert tab_view.visible is secondary
