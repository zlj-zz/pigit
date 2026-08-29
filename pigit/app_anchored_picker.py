"""
Module: pigit/app_anchored_picker.py
Description: Anchored popup list pickers for panels and diff files.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pigit.app_panel_nav import PanelNavigator
from pigit.app_theme import THEME
from pigit.termui import Segment, keys, palette
from pigit.termui.component import Component
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.primitives.frame import BoxFrame
from pigit.termui.surface import Surface
from pigit.termui.theme import get_theme, selected_row_bg
from pigit.termui.viewport_hit import (
    DoubleClickTracker,
    ViewportLayout,
    build_viewport_layout,
    hit_row,
)
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth

_INNER_W = 28
_PANEL_TITLE = "Switch panel"
_FILE_TITLE = "Files"
_FILE_INNER_W = 40

T = TypeVar("T")


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


class _AnchoredListPicker(Component, Generic[T]):
    """Framed list for an anchored ``Popup`` (shared by panel / file pickers).

    Manages ``_outer_w`` / ``outer_row_count`` so ``Popup.resize`` (full
    terminal) does not stretch the list. Subclasses supply row formatting and
    current-row marking; ``on_select`` receives the typed entry.
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
        entries: Sequence[T],
        on_select: Callable[[Any], None] | None = None,
        on_toggle: Callable[[], None] | None = None,
        title: str,
        inner_w: int = _INNER_W,
        id: str | None = None,
        initial_cursor: int | None = None,
    ) -> None:
        super().__init__(id=id)
        self._entries: list[T] = list(entries)
        self._on_select = on_select
        self._on_toggle = on_toggle
        self._title = title
        self._inner_w = inner_w
        self._cursor = 0
        if initial_cursor is not None and self._entries:
            self._cursor = max(0, min(initial_cursor, len(self._entries) - 1))
        else:
            for i in range(len(self._entries)):
                if self.is_current_at(i):
                    self._cursor = i
                    break
        self._scroll_h = max(1, len(self._entries) or 1)
        self._outer_w = inner_w + 2
        self.outer_row_count = self._scroll_h + 2
        theme = get_theme()
        self._frame = BoxFrame(
            self._inner_w,
            self._scroll_h,
            title=title,
            fg=theme.fg_primary,
            bg=theme.bg_chrome,
        )
        self._layout: ViewportLayout | None = None
        self._double_click = DoubleClickTracker()
        # Prebuilt row segments (format_row is cursor-independent); paint
        # reuses them instead of re-allocating segments every frame.
        self._row_segments = [
            self.format_row(entry, i) for i, entry in enumerate(self._entries)
        ]
        self._rebuild_geometry()

    def format_row(self, entry: T, index: int) -> list[Segment]:
        """Segments for one list row (subclass implements)."""
        raise NotImplementedError

    def is_current_at(self, index: int) -> bool:
        """Return True when ``index`` is the session's current item."""
        return False

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
        """Move cursor to the next row."""
        if not self._entries:
            return
        self._clear_double_click()
        self._cursor = min(self._cursor + 1, len(self._entries) - 1)

    def move_up(self) -> None:
        """Move cursor to the previous row."""
        if not self._entries:
            return
        self._clear_double_click()
        self._cursor = max(self._cursor - 1, 0)

    def _select_value(self) -> Any:
        """Value passed to ``on_select`` for the cursor row (subclass hook)."""
        return self._entries[self._cursor]

    def activate_selected(self) -> None:
        """Dismiss the popup, then invoke ``on_select`` for the cursor row."""
        if not self._entries:
            return
        if self._cursor < 0 or self._cursor >= len(self._entries):
            return
        self._clear_double_click()
        if self._on_toggle is not None:
            self._on_toggle()
        if self._on_select is not None:
            self._on_select(self._select_value())

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Wheel moves cursor; left click moves it; double-click activates."""
        if event.kind is not MouseKind.PRESS:
            return False
        if event.button is MouseButton.WHEEL_UP:
            self.move_up()
            return True
        if event.button is MouseButton.WHEEL_DOWN:
            self.move_down()
            return True
        if event.button is not MouseButton.LEFT:
            return False
        layout = self._layout
        if layout is None:
            return True
        origin_row, origin_col = layout.content_origin
        idx = hit_row(event.row - origin_row, event.col - origin_col, layout)
        if idx is None:
            return True
        is_double = self._double_click.is_double(idx)
        self._cursor = idx
        if is_double:
            self._clear_double_click()
            self.activate_selected()
        return True

    def _clear_double_click(self) -> None:
        self._double_click.clear()

    def _selected_row_bg(self, theme) -> tuple[int, int, int]:
        """Match the commit panel's selected-row background when available."""
        return selected_row_bg(theme)

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
        for i in range(len(self._entries)):
            row = content_row + i
            segments = self._row_segments[i]
            is_cursor = i == self._cursor
            row_bg = self._selected_row_bg(theme) if is_cursor else theme.bg_chrome
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


class PanelPicker(_AnchoredListPicker[PanelPickerEntry]):
    """Framed four-row panel list for an anchored ``Popup``."""

    def __init__(
        self,
        *,
        entries: list[PanelPickerEntry],
        on_select: Callable[[Component], None] | None = None,
        on_toggle: Callable[[], None] | None = None,
        id: str | None = None,
    ) -> None:
        self._panel_on_select = on_select

        def _select_panel(entry: PanelPickerEntry) -> None:
            if self._panel_on_select is not None:
                self._panel_on_select(entry.panel)

        super().__init__(
            entries=entries,
            on_select=_select_panel,
            on_toggle=on_toggle,
            title=_PANEL_TITLE,
            inner_w=_INNER_W,
            id=id,
        )

    def format_row(self, entry: PanelPickerEntry, index: int) -> list[Segment]:
        return format_panel_picker_row(entry)

    def is_current_at(self, index: int) -> bool:
        if index < 0 or index >= len(self._entries):
            return False
        return self._entries[index].is_current


class FilePicker(_AnchoredListPicker[str]):
    """Framed file-path list for the diff file-nav anchored ``Popup``."""

    def __init__(
        self,
        *,
        entries: list[str],
        current_index: int = 0,
        on_select: Callable[[int], None] | None = None,
        on_toggle: Callable[[], None] | None = None,
        id: str | None = None,
    ) -> None:
        self._current_index = current_index
        super().__init__(
            entries=entries,
            on_select=on_select,
            on_toggle=on_toggle,
            title=_FILE_TITLE,
            inner_w=_FILE_INNER_W,
            id=id,
            initial_cursor=current_index,
        )

    def format_row(self, entry: str, index: int) -> list[Segment]:
        is_current = self.is_current_at(index)
        marker = "● " if is_current else "  "
        return [
            Segment(marker, fg=THEME.fg_success if is_current else THEME.fg_dim),
            Segment(entry, fg=THEME.fg_muted, style_flags=palette.STYLE_BOLD),
        ]

    def is_current_at(self, index: int) -> bool:
        return index == self._current_index

    def _select_value(self) -> int:
        """Select by cursor index (stable with duplicate paths)."""
        return self._cursor
