"""
Tests for HeaderState event-driven updates.
"""

from __future__ import annotations

import pytest

from pigit.app_header_state import HeaderState
from pigit.app_theme import THEME
from pigit.termui import EventType, EVT_SELECTION_CHANGED
from pigit.termui.event_bus import EventBus
from pigit.termui.palette import STYLE_BOLD


@pytest.fixture
def header_state() -> HeaderState:
    return HeaderState(THEME)


def test_bind_to_bus_updates_mode(header_state: HeaderState) -> None:
    bus = EventBus()
    header_state.bind_to_bus(bus)

    bus.publish(EventType("mode_changed"), mode="visual")

    assert header_state.mode == "visual"


def test_bind_to_bus_updates_tab_from_active_metadata(
    header_state: HeaderState,
) -> None:
    bus = EventBus()
    header_state.bind_to_bus(bus)

    active = type("Active", (), {"tab_name": "Status", "tab_key": "1"})()
    bus.publish(EVT_SELECTION_CHANGED, active=active)

    assert header_state.tab == "Status"
    assert header_state.tab_key == "1"


def test_bind_to_bus_empty_tab_when_no_metadata(
    header_state: HeaderState,
) -> None:
    bus = EventBus()
    header_state.bind_to_bus(bus)

    active = type("Active", (), {"tab_name": "", "tab_key": ""})()
    bus.publish(EVT_SELECTION_CHANGED, active=active)

    assert header_state.tab == ""
    assert header_state.tab_key == ""


def test_bind_to_bus_unsubscribe_stops_updates(
    header_state: HeaderState,
) -> None:
    bus = EventBus()
    unsub = header_state.bind_to_bus(bus)

    bus.publish(EventType("mode_changed"), mode="visual")
    assert header_state.mode == "visual"

    unsub()
    bus.publish(EventType("mode_changed"), mode="normal")
    assert header_state.mode == "visual"


def test_left_branch_styles_without_repo_name(header_state: HeaderState) -> None:
    """Repo name is rendered by RepoSlot; left holds branch chrome only."""
    header_state.repo = "pigit"
    header_state.branch = "dev"
    gap, dot, branch = header_state.left.value[-3:]
    assert gap.text == " · "
    assert gap.fg == THEME.fg_dim
    assert dot.text == "*"
    assert dot.fg == THEME.fg_success  # clean by default
    assert branch.text == "dev"
    assert branch.fg == THEME.fg_accent
    assert branch.style_flags & STYLE_BOLD
    assert "pigit" not in "".join(s.text for s in header_state.left.value)


def test_left_appends_ahead_behind_after_branch(header_state: HeaderState) -> None:
    header_state.repo = "pigit"
    header_state.branch = "dev"
    header_state.ahead = 1
    header_state.behind = 2
    texts = [seg.text for seg in header_state.left.value]
    assert texts[-4:] == ["dev", " ", "↑1", "↓2"]
    assert header_state.left.value[-2].fg == THEME.fg_success
    assert header_state.left.value[-1].fg == THEME.fg_warning


def test_left_separator_dot_only_when_tracking(header_state: HeaderState) -> None:
    header_state.branch = "dev"
    texts = [seg.text for seg in header_state.left.value]
    assert texts[-1] == "dev"  # no arrows, no tracking gap

    header_state.behind = 2
    texts = [seg.text for seg in header_state.left.value]
    assert texts[-3:] == ["dev", " ", "↓2"]


def test_left_worktree_dot_follows_dirty_signal(header_state: HeaderState) -> None:
    header_state.branch = "dev"
    assert header_state.left.value[-2].fg == THEME.fg_success

    header_state.dirty = True
    assert header_state.left.value[-2].fg == THEME.fg_warning

    header_state.dirty = False
    assert header_state.left.value[-2].fg == THEME.fg_success


def test_repo_signal_tracks_repo_property(header_state: HeaderState) -> None:
    header_state.repo = "api"
    assert header_state.repo_signal.value == "api"


def test_right_omits_tab_text(header_state: HeaderState) -> None:
    """Tab label lives in TabSlot; right holds merge/mode badges only."""
    header_state.tab = "Status"
    header_state.tab_key = "1"
    header_state.mode = "visual"
    texts = "".join(seg.text for seg in header_state.right.value)
    assert "Status" not in texts
    assert "[1]" not in texts
    assert "[visual]" in texts


def test_tab_signals_track_properties(header_state: HeaderState) -> None:
    header_state.tab = "Branch"
    header_state.tab_key = "3"
    assert header_state.tab_signal.value == "Branch"
    assert header_state.tab_key_signal.value == "3"
