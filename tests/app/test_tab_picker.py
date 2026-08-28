# -*- coding: utf-8 -*-
"""
Module: tests/app/test_tab_picker.py
Description: PanelPicker entries, anchor formula, app wiring, overlay boundaries.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from pigit.app import PigitApplication
from pigit.app_header_state import HeaderState
from pigit.app_tab_picker import (
    PanelPicker,
    PanelPickerEntry,
    build_panel_picker_entries,
    format_panel_picker_row,
    panel_picker_anchor,
)
from pigit.app_theme import THEME
from pigit.config_data import AppConfig
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx, set_overlay_host
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.root import ComponentRoot
from pigit.termui.types import LayerKind
from pigit.termui.widgets import Popup


@pytest.fixture
def runtime():
    ctx = RuntimeContext()
    token = _runtime_ctx.set(ctx)
    yield ctx
    _runtime_ctx.reset(token)


def _mount(runtime: RuntimeContext) -> tuple[PigitApplication, ComponentRoot]:
    app = PigitApplication(config=AppConfig(repo_observe=False))
    body = app.build_root()
    root = ComponentRoot(
        body,
        runtime.registry,
        event_bus=app._event_bus,
        key_handlers=app._key_handlers,
    )
    runtime.overlay_host = root
    runtime.focus_manager = root._focus_manager
    set_overlay_host(root)
    root._app_on_event = app.on_event
    app._root = root
    app.setup_root(root)
    root.mount()
    root.resize((100, 30))
    return app, root


def test_panel_picker_anchor_default_header():
    assert panel_picker_anchor(
        header_x=1, header_y=1, header_height=2, slot_y=40, click_col=1
    ) == (2, 39)


def test_panel_picker_anchor_non_top_header():
    assert panel_picker_anchor(
        header_x=5, header_y=3, header_height=2, slot_y=10, click_col=4
    ) == (6, 14)


def test_panel_picker_anchor_right_edge_click_nudge():
    row, col = panel_picker_anchor(
        header_x=1, header_y=1, header_height=2, slot_y=70, click_col=5
    )
    assert row == 2
    assert col == 73


def test_format_panel_picker_row_marks_current():
    cur = format_panel_picker_row(
        PanelPickerEntry(Mock(), name="Status", tab_key="1", is_current=True)
    )
    other = format_panel_picker_row(
        PanelPickerEntry(Mock(), name="Stash", tab_key="2", is_current=False)
    )
    assert "".join(s.text for s in cur).startswith("● ")
    assert "".join(s.text for s in other).startswith("  ")
    assert "[1]" in "".join(s.text for s in cur)


def test_build_panel_picker_entries_from_ring():
    panels = []
    for name, key in (
        ("Status", "1"),
        ("Stash", "2"),
        ("Branch", "3"),
        ("Commit", "4"),
    ):
        p = MagicMock()
        p.tab_name = name
        p.tab_key = key
        panels.append(p)
    nav = MagicMock()
    nav.panel_ring.return_value = tuple(panels)
    nav.ring_index.return_value = 0
    entries = build_panel_picker_entries(nav)
    assert [e.panel for e in entries] == panels
    assert entries[0].is_current is True
    assert entries[1].is_current is False


def test_panel_picker_enter_selects_and_toggles():
    selected: list[object] = []
    toggled: list[int] = []
    stash_panel = Mock()
    picker = PanelPicker(
        entries=[
            PanelPickerEntry(Mock(), "Status", "1", True),
            PanelPickerEntry(stash_panel, "Stash", "2"),
        ],
        on_select=selected.append,
        on_toggle=lambda: toggled.append(1),
    )
    picker.move_down()
    picker.activate_selected()
    assert selected == [stash_panel]
    assert toggled == [1]


def test_panel_picker_double_click_activates():
    selected: list[object] = []
    stash_panel = Mock()
    picker = PanelPicker(
        entries=[
            PanelPickerEntry(Mock(), "Status", "1"),
            PanelPickerEntry(stash_panel, "Stash", "2"),
        ],
        on_select=selected.append,
        on_toggle=lambda: None,
    )
    picker.resize((40, 20))
    layout = picker._layout
    assert layout is not None
    origin_row, origin_col = layout.content_origin
    # event.row/col are 1-based local; hit_row uses event.row - origin_row.
    ev = MouseEvent(
        col=origin_col + 1,
        row=origin_row + 2,
        button=MouseButton.LEFT,
        kind=MouseKind.PRESS,
    )
    with patch(
        "pigit.app_tab_picker.time.monotonic",
        side_effect=[0.0, 0.1],
    ):
        picker.handle_mouse(ev)
        picker.handle_mouse(ev)
    assert selected == [stash_panel]


def test_panel_picker_has_outer_geometry_for_popup():
    picker = PanelPicker(entries=[PanelPickerEntry(Mock(), "Status", "1")])
    picker.resize((80, 24))
    assert picker._outer_w > 0
    assert picker.outer_row_count > 0
    popup = Popup(picker, offset=(2, 10), dismiss_on_miss=True)
    popup.resize((80, 24))
    assert picker.x == 3
    assert picker.y == 11


def test_open_panel_picker_wires_focus_destination(runtime):
    app, root = _mount(runtime)
    app._header.x = 1
    app._header.y = 1
    app._close_detail_if_open = Mock()
    dest = Mock()
    app._panel_nav.focus_destination = dest
    app._panel_nav.resolve_panel = Mock(return_value=app._status_panel)

    app.open_panel_picker(
        MouseEvent(col=1, row=1, button=MouseButton.LEFT, kind=MouseKind.PRESS)
    )
    popup = app._panel_picker_popup
    assert popup is not None
    assert popup.open is True
    assert popup.dismiss_on_miss is True
    assert root._layer_stack.top(LayerKind.MODAL) is popup

    picker = popup._child
    assert isinstance(picker, PanelPicker)
    picker.activate_selected()
    app._close_detail_if_open.assert_called()
    dest.assert_called()
    assert popup.open is False


def test_open_panel_picker_calls_dismiss_sheet(runtime):
    app, _root = _mount(runtime)
    app._header.x = 1
    app._header.y = 1
    with patch("pigit.app.dismiss_sheet") as dismiss:
        app.open_panel_picker(
            MouseEvent(col=1, row=1, button=MouseButton.LEFT, kind=MouseKind.PRESS)
        )
        dismiss.assert_called()
    assert app._panel_picker_popup is not None
    assert app._panel_picker_popup.open is True


def test_help_modal_miss_does_not_dismiss(runtime):
    app, root = _mount(runtime)
    help_popup = app._help_popup
    assert help_popup is not None
    assert help_popup.dismiss_on_miss is False
    help_popup.resize((100, 30))
    help_popup.show()
    help_popup.begin_session()

    miss = MouseEvent(col=1, row=1, button=MouseButton.LEFT, kind=MouseKind.PRESS)
    assert root._handle_mouse(miss) is True
    assert help_popup.open is True
    assert root._layer_stack.top(LayerKind.MODAL) is help_popup


def test_header_state_right_has_no_duplicate_tab():
    state = HeaderState(THEME)
    state.tab = "Status"
    state.tab_key = "1"
    text = "".join(s.text for s in state.right.value)
    assert "Status" not in text


def test_esc_closes_panel_picker(runtime):
    app, root = _mount(runtime)
    app._header.x = 1
    app._header.y = 1
    app.open_panel_picker(
        MouseEvent(col=1, row=1, button=MouseButton.LEFT, kind=MouseKind.PRESS)
    )
    popup = app._panel_picker_popup
    assert popup is not None and popup.open
    root._handle_event("esc")
    assert popup.open is False
    assert root._layer_stack.top(LayerKind.MODAL) is None
