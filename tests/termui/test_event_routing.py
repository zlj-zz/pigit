"""
Module: tests/termui/test_event_routing.py
Description: Tests for focus-based event routing in the TUI framework.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pigit.termui._component import Component
from pigit.termui.containers import Column, Row, TabView
from pigit.termui._root import ComponentRoot
from pigit.termui.types import OverlayDispatchResult
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx


@pytest.fixture(autouse=True)
def _runtime_context():
    """Provide a fresh RuntimeContext for event routing tests."""
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    yield
    _runtime_ctx.reset(token)


# --- Helpers ---


def _make_root(body):
    """Create a ComponentRoot and wire it into the current RuntimeContext."""
    from pigit.termui._root import ComponentRoot

    root = ComponentRoot(body)
    runtime = RuntimeContext.current()
    if runtime is not None:
        runtime.overlay_host = root
        runtime.focus_manager = root._focus_manager
    return root


class _RecordingLeaf(Component):
    """Leaf component that records received keys."""

    def __init__(self, label: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.label = label
        self.received_keys: list[str] = []

    def _handle_event(self, key: str) -> None:
        self.received_keys.append(key)

    def _render_surface(self, surface) -> None:
        pass


class _NoHandleEventLeaf(Component):
    """Leaf component without _handle_event override."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def _render_surface(self, surface) -> None:
        pass


# --- T012: Focus leaf dispatch ---


class TestFocusLeafDispatch:
    def test_key_reaches_focus_leaf(self):
        """A key event dispatched by ComponentRoot reaches the focused leaf."""
        leaf = _RecordingLeaf("target", id="leaf")
        root = _make_root(leaf)
        root.resize((20, 10))

        root._focus_manager.set_focus_chain(leaf)
        root._handle_event("j")

        assert leaf.received_keys == ["j"]

    def test_key_does_not_reach_unfocused_leaf(self):
        """A key event does not reach a leaf that is not on the focus chain."""
        focused = _RecordingLeaf("focused", id="focused")
        unfocused = _RecordingLeaf("unfocused", id="unfocused")
        column = Column(children=[focused, unfocused], heights=[1, 1])
        root = _make_root(column)
        root.resize((20, 10))

        root._focus_manager.set_focus_chain(focused)
        root._handle_event("k")

        assert focused.received_keys == ["k"]
        assert unfocused.received_keys == []

    def test_container_without_handle_event_does_not_break_dispatch(self):
        """A container child without _handle_event does not break focus leaf dispatch."""
        leaf = _RecordingLeaf("target", id="leaf")
        no_handler = _NoHandleEventLeaf(id="no_handler")
        column = Column(children=[no_handler, leaf], heights=[1, 1])
        root = _make_root(column)
        root.resize((20, 10))

        root._focus_manager.set_focus_chain(leaf)
        root._handle_event("x")

        assert leaf.received_keys == ["x"]


# --- T013: Tab switch focus update ---


class TestTabSwitchFocus:
    def test_tab_switch_updates_focus(self):
        """When TabView switches active child, focus moves to the new leaf."""
        main = _RecordingLeaf("main", id="main")
        secondary = _RecordingLeaf("secondary", id="secondary")
        tab_view = TabView(children=[main, secondary], start="main")
        root = _make_root(tab_view)
        root.resize((20, 10))

        # Initially main is active and focused
        root._handle_event("j")
        assert main.received_keys == ["j"]
        assert secondary.received_keys == []

        # Switch to secondary
        tab_view.route_to("secondary")

        # Key should now reach secondary
        root._handle_event("k")
        assert secondary.received_keys == ["k"]
        # main should not receive the second key
        assert main.received_keys == ["j"]

    def test_tab_switch_focus_chain_levels(self):
        """After tab switch, focus levels are set correctly on the new chain."""
        main = _RecordingLeaf("main", id="main")
        secondary = _RecordingLeaf("secondary", id="secondary")
        tab_view = TabView(children=[main, secondary], start="main")
        root = _make_root(tab_view)
        root.resize((20, 10))

        assert main._focus_level == 0
        assert tab_view._focus_level == 1
        assert secondary._focus_level == -1

        tab_view.route_to("secondary")

        assert secondary._focus_level == 0
        assert tab_view._focus_level == 1
        assert main._focus_level == -1


# --- T014: Overlay focus takeover ---


class TestOverlayFocusTakeover:
    def test_overlay_receives_focus_when_open(self):
        """When an overlay is open, keys are dispatched to it instead of the body."""
        body_leaf = _RecordingLeaf("body", id="body")
        root = _make_root(body_leaf)
        root.resize((20, 10))

        # Monkey-patch overlay dispatch to simulate an open overlay
        original_try_dispatch = root.try_dispatch_overlay
        root.try_dispatch_overlay = lambda key: (
            OverlayDispatchResult.HANDLED_EXPLICIT
            if key == "x"
            else original_try_dispatch(key)
        )

        # Before overlay: key reaches body
        root._handle_event("j")
        assert body_leaf.received_keys == ["j"]

        # Simulate overlay open by making has_overlay_open return True
        original_has_overlay = root.has_overlay_open
        root.has_overlay_open = lambda: True

        # After overlay opens: same key should be dispatched via overlay path
        root._handle_event("x")
        # The overlay path calls _handle_event on root which then tries dispatch again
        # Since we patched try_dispatch_overlay to return HANDLED_EXPLICIT for "x",
        # the key is consumed by the overlay path

        # body should not receive "x"
        assert "x" not in body_leaf.received_keys

        # Cleanup
        root.has_overlay_open = original_has_overlay
        root.try_dispatch_overlay = original_try_dispatch

    def test_focus_manager_tracks_overlay(self):
        """FocusManager.set_focus_chain is called with the overlay component."""
        body_leaf = _RecordingLeaf("body", id="body")
        root = _make_root(body_leaf)
        root.resize((20, 10))

        # Create a fake overlay component
        overlay = _RecordingLeaf("overlay", id="overlay")

        # Monkey-patch _top_open_overlay to return our fake overlay
        root._top_open_overlay = lambda: overlay
        root.has_overlay_open = lambda: True
        root.try_dispatch_overlay = lambda key: OverlayDispatchResult.HANDLED_EXPLICIT

        root._focus_manager.set_focus_chain = MagicMock(
            wraps=root._focus_manager.set_focus_chain
        )
        root._handle_event("x")

        # Focus should have been set to the overlay
        root._focus_manager.set_focus_chain.assert_any_call(overlay)


# --- T016-T019: Panel navigation integration ---


class _BoundLeaf(Component):
    """Leaf component with key bindings."""

    BINDINGS = [("j", "on_j")]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.j_pressed = False

    def on_j(self) -> None:
        self.j_pressed = True

    def _render_surface(self, surface) -> None:
        pass


class TestPanelNavigationIntegration:
    def test_bindings_work_through_tabview(self):
        """Key bindings on a leaf inside TabView are triggered via focus leaf dispatch."""
        leaf = _BoundLeaf(id="leaf")
        tab_view = TabView(children=[leaf], start="leaf")
        root = _make_root(tab_view)
        root.resize((20, 10))

        root._handle_event("j")
        assert leaf.j_pressed is True

    def test_bindings_only_on_active_tab(self):
        """Only the active tab's bindings are triggered; inactive tabs receive nothing."""
        active = _BoundLeaf(id="active")
        inactive = _BoundLeaf(id="inactive")
        tab_view = TabView(children=[active, inactive], start="active")
        root = _make_root(tab_view)
        root.resize((20, 10))

        root._handle_event("j")
        assert active.j_pressed is True
        assert inactive.j_pressed is False

        tab_view.route_to("inactive")
        root._handle_event("j")
        assert inactive.j_pressed is True


# --- T015: Column child without focus receives no events ---


class TestColumnNoBroadcast:
    def test_column_child_without_focus_receives_no_events(self):
        """Only the focused child in a Column receives key events."""
        child_a = _RecordingLeaf("a", id="a")
        child_b = _RecordingLeaf("b", id="b")
        child_c = _RecordingLeaf("c", id="c")
        column = Column(children=[child_a, child_b, child_c], heights=[1, 1, 1])
        root = _make_root(column)
        root.resize((20, 10))

        # Focus child_b
        root._focus_manager.set_focus_chain(child_b)
        root._handle_event("k")

        assert child_a.received_keys == []
        assert child_b.received_keys == ["k"]
        assert child_c.received_keys == []

    def test_row_child_without_focus_receives_no_events(self):
        """Only the focused child in a Row receives key events."""
        child_a = _RecordingLeaf("a", id="a")
        child_b = _RecordingLeaf("b", id="b")
        row = Row(children=[child_a, child_b], widths=[10, 10])
        root = _make_root(row)
        root.resize((20, 10))

        # Focus child_a
        root._focus_manager.set_focus_chain(child_a)
        root._handle_event("j")

        assert child_a.received_keys == ["j"]
        assert child_b.received_keys == []

    def test_nested_container_focus_routing(self):
        """Focus routing works through nested containers."""
        inner_leaf = _RecordingLeaf("inner", id="inner")
        inner_column = Column(children=[inner_leaf], heights=[1])
        outer_row = Row(children=[inner_column], widths=[20])
        root = _make_root(outer_row)
        root.resize((20, 10))

        root._focus_manager.set_focus_chain(inner_leaf)
        root._handle_event("q")

        assert inner_leaf.received_keys == ["q"]
