# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_header_slot.py
Description: HeaderSlot shared truncate, refresh, click, and display-name hooks.
Author: Zev
Date: 2026-08-29
"""

from __future__ import annotations

from unittest.mock import patch

from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.reactive import Signal
from pigit.termui.surface import Surface
from pigit.termui.widgets.header_slot import HeaderSlot, _SUFFIX
from pigit.termui.wcwidth_table import wcswidth


class _ProbeSlot(HeaderSlot):
    """Minimal concrete slot for base-class coverage."""

    def __init__(self, *, sources, on_click=None, fg=None, id=None):
        super().__init__(sources=sources, fg=fg, id=id)
        self._clicks: list[MouseEvent] = []
        self._on_click = on_click

    def _assemble(self, display_name: str) -> str:
        return f"<{display_name}>{_SUFFIX}"

    def _fixed_width(self) -> int:
        return wcswidth("<>") + wcswidth(_SUFFIX)

    def _default_fg(self) -> tuple[int, int, int]:
        return (1, 2, 3)

    def _handle_click(self, event: MouseEvent) -> None:
        self._clicks.append(event)
        if self._on_click is not None:
            self._on_click(event)


def test_display_name_is_sources_zero():
    slot = _ProbeSlot(sources=["alpha", "beta"])
    assert slot._display_name() == "alpha"
    assert slot._values() == ["alpha", "beta"]


def test_refresh_requests_render():
    slot = _ProbeSlot(sources=["x"])
    with patch("pigit.termui.widgets.header_slot.request_render") as req:
        slot.refresh()
        req.assert_called_once()


def test_left_click_calls_handle_click():
    slot = _ProbeSlot(sources=["x"])
    ev = MouseEvent(col=1, row=1, button=MouseButton.LEFT, kind=MouseKind.PRESS)
    assert slot.handle_mouse(ev) is True
    assert slot._clicks == [ev]


def test_narrow_slot_truncates_with_ellipsis():
    slot = _ProbeSlot(sources=["abcdefghij"])
    full = slot.as_segments()[0].text
    assert full == f"<abcdefghij>{_SUFFIX}"
    slot.resize((8, 1))
    surface = Surface(8, 1)
    slot.paint(surface)
    line = surface.lines()[0]
    assert "…" in line or len(line.strip()) <= 8
    assert wcswidth(line.rstrip()) <= 8


def test_signal_source_updates_display_name():
    name = Signal("Status")
    slot = _ProbeSlot(sources=[name])
    assert slot._display_name() == "Status"
    name.set("Stash")
    assert slot._display_name() == "Stash"


def test_preferred_width_caps_at_max():
    slot = _ProbeSlot(sources=["alpha"])
    full = f"<alpha>{_SUFFIX}"
    assert slot.preferred_width() == wcswidth(full)
    assert slot.preferred_width(max_width=5) == 5


def test_as_segments_text_and_default_fg_fallback():
    slot = _ProbeSlot(sources=["alpha"])  # fg=None → _default_fg hook
    seg = slot.as_segments()[0]
    assert seg.text == f"<alpha>{_SUFFIX}"
    assert seg.fg == (1, 2, 3)


def test_destroy_clears_signal_unsubs():
    name = Signal("Status")
    slot = _ProbeSlot(sources=[name])
    assert len(slot._unsubs) == 1
    slot.destroy()
    assert slot._unsubs == []
