"""
Module: pigit/app_tab_picker.py
Description: Anchored popup UI for switching among the four product panels.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from pigit.app_panel_nav import PanelNavigator
from pigit.app_theme import THEME
from pigit.termui import Segment, keys, palette
from pigit.termui.component import Component
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.primitives.frame import BoxFrame
from pigit.termui.surface import Surface
from pigit.termui.theme import get_theme
from pigit.termui.viewport_hit import (
    DOUBLE_CLICK_MS,
    ViewportLayout,
    build_viewport_layout,
    hit_row,
)
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth

_INNER_W = 28
_TITLE = "Switch panel"


def panel_picker_anchor(
    *,
    header_x: int,
    header_y: int,
    header_height: int,
    slot_y: int,
    click_col: int = 1,
) -> tuple[int, int]:
    """Compute 0-based Popup ``offset`` from Header + TabSlot geometry.

    Places the popup below the full header strip (including separator). Optional
    ``click_col`` is the 1-based local column inside the slot.
    """
    anchor_row = (header_x - 1) + header_height
    anchor_col = (header_y - 1) + (slot_y - 1) + (click_col - 1)
    return anchor_row, anchor_col


@dataclass(frozen=True)
class PanelPickerEntry:
    """One selectable row in the panel picker."""

    panel: Component
    name: str
    tab_key: str
    is_current: bool = False


def build_panel_picker_entries(panel_nav: PanelNavigator) -> list[PanelPickerEntry]:
    """Build the product-panel rows from ``panel_ring()`` (no HeaderState copy).

    The row carries the panel itself, so switching goes straight to
    ``focus_destination(panel)`` — no hardcoded id table to drift.
    """
    ring = panel_nav.panel_ring()
    if not ring:
        return []
    current_idx = panel_nav.ring_index()
    entries: list[PanelPickerEntry] = []
    for idx, panel in enumerate(ring):
        entries.append(
            PanelPickerEntry(
                panel=panel,
                name=panel.tab_name or "",
                tab_key=panel.tab_key or "",
                is_current=current_idx is not None and idx == current_idx,
            )
        )
    return entries


def format_panel_picker_row(entry: PanelPickerEntry) -> list[Segment]:
    """Segments for one picker row: ``● Name  [key]`` (or two spaces when not current)."""
    marker = "● " if entry.is_current else "  "
    segs: list[Segment] = [
        Segment(marker, fg=THEME.fg_success if entry.is_current else THEME.fg_dim),
        Segment(entry.name, fg=THEME.fg_muted, style_flags=palette.STYLE_BOLD),
    ]
    if entry.tab_key:
        segs.append(Segment(f"  [{entry.tab_key}]", fg=THEME.fg_primary))
    return segs


class PanelPicker(Component):
    """Framed four-row panel list for an anchored ``Popup`` (BindingBrowser chrome).

    Manages ``_outer_w`` / ``outer_row_count`` itself so ``Popup.resize`` (full
    terminal) does not leave a bare OptionList at screen size. No ``/`` filter —
    four rows use ``j/k`` + Enter / double-click only.
    """

    BINDINGS = [
        (keys.KEY_DOWN, "move_down"),
        (keys.KEY_UP, "move_up"),
        ("j", "move_down"),
        ("k", "move_up"),
        (keys.KEY_ENTER, "activate_selected"),
    ]

    def __init__(
        self,
        *,
        entries: list[PanelPickerEntry],
        on_select: Callable[[Component], None] | None = None,
        on_toggle: Callable[[], None] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._entries = list(entries)
        self._on_select = on_select
        self._on_toggle = on_toggle
        self._cursor = 0
        for i, entry in enumerate(self._entries):
            if entry.is_current:
                self._cursor = i
                break
        self._inner_w = _INNER_W
        self._scroll_h = max(1, len(self._entries) or 1)
        self._outer_w = _INNER_W + 2
        self.outer_row_count = self._scroll_h + 2
        theme = get_theme()
        self._frame = BoxFrame(
            self._inner_w,
            self._scroll_h,
            title=_TITLE,
            fg=theme.fg_primary,
            bg=theme.bg_chrome,
        )
        self._layout: ViewportLayout | None = None
        self._last_click_index: int | None = None
        self._last_click_time = 0.0
        self._rebuild_geometry()

    def set_on_toggle(self, cb: Callable[[], None] | None) -> None:
        """Wire the wrapping Popup's toggle (called from Popup.__init__)."""
        self._on_toggle = cb

    def toggle(self) -> None:
        """Dismiss via the Popup shell when wired."""
        self._clear_double_click()
        if self._on_toggle is not None:
            self._on_toggle()

    def get_footer_entries(self) -> list[tuple[str, str]]:
        """Footer hints while the picker owns the keyboard."""
        return [
            ("j/k", "Navigate"),
            ("enter", "Switch"),
            ("esc", "Close"),
        ]

    def resize(self, size: tuple[int, int]) -> None:
        """Ignore full-terminal size; keep compact framed geometry (Popup contract).

        Double-click state is only cleared when geometry actually changed, so a
        terminal resize mid-double-click does not silently eat the second press.
        """
        old_geometry = (self._outer_w, self.outer_row_count)
        self._rebuild_geometry()
        if (self._outer_w, self.outer_row_count) != old_geometry:
            self._clear_double_click()
        super().resize(size)

    def _rebuild_geometry(self) -> None:
        n = max(1, len(self._entries))
        self._scroll_h = n
        self._inner_w = _INNER_W
        self._frame.set_inner_size(self._inner_w, self._scroll_h)
        self._outer_w = self._frame.outer_width
        self.outer_row_count = self._frame.outer_height
        cr, cc, cw, _ch = self._frame.content_rect(0, 0)
        selectable = list(range(len(self._entries)))
        self._layout = build_viewport_layout(
            selectable,
            content_origin=(cr, cc),
            content_width=cw,
            viewport_height=self._scroll_h,
            scroll_offset=0,
        )

    def move_down(self) -> None:
        """Move cursor to the next panel row."""
        if not self._entries:
            return
        self._clear_double_click()
        self._cursor = min(self._cursor + 1, len(self._entries) - 1)

    def move_up(self) -> None:
        """Move cursor to the previous panel row."""
        if not self._entries:
            return
        self._clear_double_click()
        self._cursor = max(self._cursor - 1, 0)

    def activate_selected(self) -> None:
        """Dismiss the popup, then invoke ``on_select`` for the cursor row."""
        if not self._entries:
            return
        if self._cursor < 0 or self._cursor >= len(self._entries):
            return
        entry = self._entries[self._cursor]
        self._clear_double_click()
        if self._on_toggle is not None:
            self._on_toggle()
        if self._on_select is not None:
            self._on_select(entry.panel)

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Left click moves cursor; double-click activates (viewport_hit)."""
        if event.kind is not MouseKind.PRESS:
            return False
        if event.button is not MouseButton.LEFT:
            return False
        layout = self._layout
        if layout is None:
            return True
        origin_row, origin_col = layout.content_origin
        idx = hit_row(event.row - origin_row, event.col - origin_col, layout)
        if idx is None:
            return True
        now = time.monotonic()
        is_double = (
            idx == self._last_click_index
            and now - self._last_click_time <= DOUBLE_CLICK_MS / 1000.0
        )
        self._last_click_index = idx
        self._last_click_time = now
        self._cursor = idx
        if is_double:
            self._clear_double_click()
            self.activate_selected()
        return True

    def _clear_double_click(self) -> None:
        self._last_click_index = None
        self._last_click_time = 0.0

    def paint(self, surface: Surface) -> None:
        """Draw the framed list with the cursor row highlighted."""
        theme = get_theme()
        self._frame.fg = theme.fg_primary
        self._frame.bg = theme.bg_chrome
        surface.fill_rect_rgb(
            0, 0, self._outer_w, self.outer_row_count, theme.bg_chrome
        )
        self._frame.draw(surface, 0, 0)
        content_row, content_col, cw, _ch = self._frame.content_rect(0, 0)
        for i, entry in enumerate(self._entries):
            row = content_row + i
            segments = format_panel_picker_row(entry)
            is_cursor = i == self._cursor
            row_bg = theme.bg_hover if is_cursor else theme.bg_chrome
            if is_cursor:
                surface.fill_rect_rgb(row, content_col, cw, 1, row_bg)
            x = content_col
            for seg in segments:
                text = seg.text
                text_w = wcswidth(text)
                avail = content_col + cw - x
                if text_w > avail:
                    text = truncate_by_width(text, avail)
                surface.draw_text_rgb(
                    row,
                    x,
                    text,
                    fg=seg.fg,
                    bg=row_bg if is_cursor else seg.bg,
                    style_flags=seg.style_flags,
                )
                x += wcswidth(text)
