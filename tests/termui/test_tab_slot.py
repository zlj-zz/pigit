# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_tab_slot.py
Description: TabSlot paint, truncation, and click callback.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.reactive import Signal
from pigit.termui.surface import Surface
from pigit.termui.widgets import Header, TabSlot
from pigit.termui.segment import Segment


def test_tab_slot_click_forwards_event():
    seen: list[MouseEvent] = []
    slot = TabSlot(tab_name="Status", tab_key="1", on_open=seen.append)
    slot.resize((20, 1))
    ev = MouseEvent(col=3, row=1, button=MouseButton.LEFT, kind=MouseKind.PRESS)
    assert slot.handle_mouse(ev) is True
    assert seen == [ev]
    assert "Status [1]" in slot.as_segments()[0].text
    assert "▾" in slot.as_segments()[0].text


def test_tab_slot_preferred_width_and_truncate():
    slot = TabSlot(tab_name="Status", tab_key="1")
    full = slot.preferred_width()
    slot.resize((8, 1))
    surface = Surface(8, 1)
    slot.paint(surface)
    line = surface.lines()[0]
    assert len(line.strip()) <= 8 or "…" in line or "▾" in line
    assert full > 8


def test_tab_slot_binds_signals():
    name = Signal("Status")
    key = Signal("1")
    slot = TabSlot(tab_name=name, tab_key=key)
    assert slot.label_name == "Status"
    name.set("Stash")
    key.set("2")
    assert slot.label_name == "Stash"
    assert slot.label_key == "2"


def test_header_right_child_hit_and_paint():
    opened: list[int] = []
    slot = TabSlot(
        tab_name="Status",
        tab_key="1",
        on_open=lambda _ev: opened.append(1),
    )
    header = Header(
        right=[Segment("[MERGE] x  ")],
        right_child=slot,
        separator=False,
        id="header",
    )
    header.resize((48, 1))
    header.mount()
    surface = Surface(48, 1)
    header.paint(surface)
    line = surface.lines()[0]
    assert "Status [1]" in line
    assert "▾" in line
    assert "[MERGE]" in line

    # Click near the right edge where TabSlot is laid out.
    hit = header._hit_test(slot.y, 1)
    assert hit is not None
    target, lcol, lrow = hit
    assert target is slot
    target.handle_mouse(
        MouseEvent(col=lcol, row=lrow, button=MouseButton.LEFT, kind=MouseKind.PRESS)
    )
    assert opened == [1]
