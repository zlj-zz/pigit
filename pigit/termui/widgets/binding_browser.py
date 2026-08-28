"""
Module: pigit/termui/widgets/binding_browser.py
Description: Selectable executable binding list for Help / action browser popups.
Author: Zev
Date: 2026-08-27
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence

from .. import keys, palette
from ..bindings import ExecutableBinding
from ..component import Component
from .._layout import Padding
from ..mouse import MouseButton, MouseEvent, MouseKind
from ..primitives.frame import BoxFrame
from ..segment import Segment
from ..surface import Surface
from ..theme import get_theme
from ..viewport_hit import (
    DOUBLE_CLICK_MS,
    ViewportLayout,
    build_viewport_layout,
    hit_row,
)
from ..wcwidth_table import truncate_by_width, wcswidth
from .help_format import build_binding_browser_lines, _CURSOR_COL_W, _CURSOR_GLYPH

_logger = logging.getLogger(__name__)

# Cursor glyph width is reserved on every entry's first render line.
_DISMISS_ONLY_ACTION = "universal.help"


def _is_dismiss_only_action(action: str) -> bool:
    """True for the app-level Help toggle row."""
    return action == _DISMISS_ONLY_ACTION


class BindingBrowser(Component):
    """Grouped executable bindings with a cursor; wrap in ``Popup`` for modality.

    One ``ExecutableBinding`` is one selectable entry; wrapped description lines
    are non-selectable continuations. Enter dismisses via ``on_toggle`` then
    invokes (except dismiss-only help rows).
    """

    MIN_INNER_W = 88
    MAX_INNER_W = 158
    WHEEL_SCROLL_LINES = 1

    BINDINGS = [
        (keys.KEY_DOWN, "move_down"),
        (keys.KEY_UP, "move_up"),
        ("j", "move_down"),
        ("k", "move_up"),
        (keys.KEY_ENTER, "activate_selected"),
        ("?", "toggle"),
    ]

    def __init__(
        self,
        inner_width: int | None = None,
        inner_height: int | None = None,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        *,
        key_fg: tuple[int, int, int] | None = None,
        on_toggle: Callable[[], None] | None = None,
        on_invoke_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        super().__init__(x=x, y=y, size=size)
        self._inner_w_cfg = inner_width
        self._inner_h_cfg = inner_height
        self._key_fg = key_fg
        self._on_toggle = on_toggle
        self._on_invoke_error = on_invoke_error
        self._groups: list[tuple[str, list[ExecutableBinding]]] = []
        self._selectable: list[ExecutableBinding] = []
        self._cursor = 0
        self._offset = 0
        self._inner_w = 40
        self._scroll_h = 6
        self._outer_w = 42
        self.outer_row_count = 10
        theme = get_theme()
        self._frame = BoxFrame(
            0, 0, title="Help   esc close", fg=theme.fg_primary, bg=theme.bg_chrome
        )
        self._padding = Padding(top=2, right=4, bottom=2, left=4)
        # (segments, selectable_index | None) — None for headers / blank / wraps
        self._render: list[tuple[list[Segment], int | None]] = []
        # Viewport hit geometry rebuilt alongside ``_render`` (see _rebuild).
        self._layout: ViewportLayout | None = None
        # Last left press, for double-click detection (cleared on dismiss/reset).
        self._last_click_index: int | None = None
        self._last_click_time = 0.0

    def set_on_toggle(self, cb: Callable[[], None] | None) -> None:
        """Set the callback invoked by :meth:`toggle` (Popup wires this)."""
        self._on_toggle = cb

    def toggle(self) -> None:
        """Delegate toggle to the wrapping popup shell, if any."""
        self._clear_double_click()
        if self._on_toggle is not None:
            self._on_toggle()

    def get_footer_entries(self) -> list[tuple[str, str]]:
        """Footer hints while the Help browser modal owns the keyboard."""
        from ..bindings import merge_footer_pairs

        return merge_footer_pairs(
            [
                ("j", "Navigate"),
                ("k", "Navigate"),
                (keys.KEY_DOWN, "Navigate"),
                (keys.KEY_UP, "Navigate"),
                (keys.KEY_ENTER, "Run"),
                ("?", "Close"),
            ]
        )

    def set_groups(
        self,
        groups: Sequence[tuple[str, Sequence[ExecutableBinding]]],
    ) -> None:
        """Replace grouped bindings and reset cursor / scroll / click state."""
        self._groups = [(title, list(entries)) for title, entries in groups]
        self._clear_double_click()
        self._rebuild_selectable()
        self._rebuild()
        self._cursor = 0
        self._ensure_cursor_visible()

    def _rebuild_selectable(self) -> None:
        self._selectable = []
        for _title, entries in self._groups:
            self._selectable.extend(entries)

    def selected_binding(self) -> ExecutableBinding | None:
        """Return the cursor row, or None when the list is empty."""
        if not self._selectable:
            return None
        if self._cursor < 0 or self._cursor >= len(self._selectable):
            return None
        return self._selectable[self._cursor]

    def move_down(self) -> None:
        """Move cursor to the next selectable entry (clamped)."""
        if not self._selectable:
            return
        self._clear_double_click()
        self._cursor = min(self._cursor + 1, len(self._selectable) - 1)
        self._ensure_cursor_visible()

    def move_up(self) -> None:
        """Move cursor to the previous selectable entry (clamped)."""
        if not self._selectable:
            return
        self._clear_double_click()
        self._cursor = max(self._cursor - 1, 0)
        self._ensure_cursor_visible()

    def activate_selected(self) -> None:
        """Dismiss the popup, then invoke the selected binding (unless dismiss-only)."""
        entry = self.selected_binding()
        if entry is None:
            return
        self._clear_double_click()
        dismiss_only = _is_dismiss_only_action(entry.action)
        if self._on_toggle is not None:
            self._on_toggle()
        if dismiss_only:
            return
        try:
            entry.invoke()
        except Exception as exc:
            _logger.exception("Help binding invoke failed: %s", entry.action)
            if self._on_invoke_error is not None:
                self._on_invoke_error(exc)

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Wheel scrolls; a left click moves the cursor, a double-click activates."""
        if event.kind is not MouseKind.PRESS:
            return False
        if event.button is MouseButton.WHEEL_UP:
            self._scroll_up(self.WHEEL_SCROLL_LINES)
            return True
        if event.button is MouseButton.WHEEL_DOWN:
            self._scroll_down(self.WHEEL_SCROLL_LINES)
            return True
        if event.button is MouseButton.LEFT:
            return self._handle_left_press(event)
        return False

    def _handle_left_press(self, event: MouseEvent) -> bool:
        """Move the cursor to the clicked selectable row; double-click activates.

        Clicks on group headers, blank separators, wrapped continuations or
        the frame border are consumed without moving the cursor or dismissing
        (mirrors how a modal swallows clicks that miss it).
        """
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
        self._ensure_cursor_visible()
        if is_double:
            self._clear_double_click()
            self.activate_selected()
        return True

    def _clear_double_click(self) -> None:
        """Forget the previous left press (used on dismiss and content reset)."""
        self._last_click_index = None
        self._last_click_time = 0.0

    def _scroll_down(self, line: int = 1) -> None:
        max_off = max(0, len(self._render) - self._scroll_h)
        new_off = min(self._offset + max(1, line), max_off)
        if new_off != self._offset:
            self._offset = new_off
            self._clear_double_click()
            self._rebuild_layout()

    def _scroll_up(self, line: int = 1) -> None:
        new_off = max(0, self._offset - max(1, line))
        if new_off != self._offset:
            self._offset = new_off
            self._clear_double_click()
            self._rebuild_layout()

    def _cursor_primary_render_index(self) -> int | None:
        for i, (_segs, sel_i) in enumerate(self._render):
            if sel_i == self._cursor:
                return i
        return None

    def _ensure_cursor_visible(self) -> None:
        idx = self._cursor_primary_render_index()
        if idx is None:
            return
        new_off = self._offset
        if idx < new_off:
            new_off = idx
        elif idx >= new_off + self._scroll_h:
            new_off = idx - self._scroll_h + 1
        if new_off != self._offset:
            self._offset = new_off
            self._rebuild_layout()

    def _estimate_content_width(self) -> int:
        gap = 2
        group_indent = 2
        max_key_w = 0
        desc_lengths: list[int] = []
        for _title, entries in self._groups:
            for row in entries:
                max_key_w = max(max_key_w, wcswidth(row.keys_display))
                desc_lengths.append(wcswidth(row.desc))
        if not desc_lengths:
            return 0
        avg_desc = sum(desc_lengths) // len(desc_lengths)
        desc_w = min(max(avg_desc, 16), 40)
        return group_indent + _CURSOR_COL_W + max_key_w + gap + desc_w

    def resize(self, size: tuple[int, int]) -> None:
        """Recalculate inner and outer dimensions for the given terminal size.

        A terminal resize must not let a click before the resize pair with one
        after it; clear the double-click window like other lifecycle resets.
        """
        self._clear_double_click()
        tw, th = int(size[0]), int(size[1])
        avail_w, avail_h = self._padding.apply((tw, th))

        if self._inner_w_cfg is not None:
            inner_w = self._inner_w_cfg
        else:
            content_w = self._estimate_content_width()
            if content_w:
                inner_w = max(
                    self.MIN_INNER_W,
                    min(content_w, self.MAX_INNER_W, avail_w),
                )
            else:
                inner_w = max(self.MIN_INNER_W, min(self.MAX_INNER_W, avail_w))

        inner_h = (
            self._inner_h_cfg if self._inner_h_cfg is not None else max(8, th // 2)
        )
        inner_w = max(16, min(inner_w, avail_w))
        inner_h = max(5, min(inner_h, avail_h))
        self._inner_w = inner_w
        self._scroll_h = max(1, inner_h - 1)
        self._frame.set_inner_size(self._inner_w, self._scroll_h)
        self._outer_w = self._frame.outer_width
        self.outer_row_count = self._frame.outer_height
        super().resize(size)
        self._rebuild()
        self._ensure_cursor_visible()

    def _rebuild(self) -> None:
        """Rebuild paint lines and the viewport layout from current ``_inner_w``."""
        self._render = self._build_grouped(self._groups)
        max_off = max(0, len(self._render) - self._scroll_h)
        self._offset = min(self._offset, max_off)
        self._rebuild_layout()

    def _rebuild_layout(self) -> None:
        """Project the current paint lines and ``_offset`` into viewport geometry.

        Pure geometry (no text wrapping), so it may rerun whenever ``_offset``
        changes; paint and hit always read the same scroll position.
        """
        cr, cc, cw, _ch = self._frame.content_rect(0, 0)
        self._layout = build_viewport_layout(
            [sel for _segs, sel in self._render],
            content_origin=(cr, cc),
            content_width=cw,
            viewport_height=self._scroll_h,
            scroll_offset=self._offset,
        )

    def _build_grouped(
        self, groups: list[tuple[str, list[ExecutableBinding]]]
    ) -> list[tuple[list[Segment], int | None]]:
        return build_binding_browser_lines(
            groups,
            inner_width=self._inner_w,
            key_fg=self._key_fg,
            show_cursor=True,
        )

    def _selected_row_bg(self, theme) -> tuple[int, int, int]:
        """Match commit-panel cursor row when ``PigitTheme`` is installed."""
        selected = getattr(theme, "bg_commit_selected", None)
        if selected is not None:
            return selected
        return theme.bg_hover

    def paint(self, surface: Surface) -> None:
        theme = get_theme()
        self._frame.fg = theme.fg_primary
        self._frame.bg = theme.bg_chrome
        surface.fill_rect_rgb(
            0, 0, self._outer_w, self.outer_row_count, theme.bg_chrome
        )
        self._frame.draw(surface, 0, 0)

        content_row, content_col, cw, _ch = self._frame.content_rect(0, 0)
        chunk = self._render[self._offset : self._offset + self._scroll_h]
        for i, (segments, sel_i) in enumerate(chunk):
            row = content_row + i
            is_cursor = sel_i is not None and sel_i == self._cursor
            row_bg = self._selected_row_bg(theme) if is_cursor else theme.bg_chrome
            if is_cursor and segments:
                painted: list[Segment] = []
                replaced = False
                for seg in segments:
                    if (
                        not replaced
                        and seg.text == " " * _CURSOR_COL_W
                        and seg.fg is None
                    ):
                        painted.append(
                            Segment(
                                f"{_CURSOR_GLYPH} ",
                                fg=theme.fg_accent,
                                bg=row_bg,
                            )
                        )
                        replaced = True
                    else:
                        painted.append(
                            Segment(
                                seg.text,
                                fg=seg.fg,
                                bg=row_bg,
                                style_flags=seg.style_flags,
                            )
                        )
                segments = painted

            x = content_col
            if is_cursor:
                surface.fill_rect_rgb(row, content_col, cw, 1, row_bg)
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
                    bg=(
                        seg.bg
                        if seg.bg is not None
                        else (row_bg if is_cursor else None)
                    ),
                    style_flags=seg.style_flags,
                )
                x += wcswidth(text)
            if x < content_col + cw and not is_cursor:
                surface.fill_rect_rgb(row, x, content_col + cw - x, 1, theme.bg_chrome)
