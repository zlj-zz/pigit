"""
Module: pigit/termui/widgets/item_list.py
Description: List selector widget with cursor and scroll viewport.
Author: Zev
Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import logging

from .. import keys, palette
from ..theme import get_theme
from ..component import Component, ComponentError, is_on_visible_paint_path
from ..mouse import MouseButton, MouseKind, MouseEvent
from .._runtime_context import request_render
from ..segment import Segment
from ..surface import Surface
from ..reactive import Signal
from ..types import EVT_SELECTION_CHANGED
from ..wcwidth_table import truncate_by_width, wcswidth

_logger = logging.getLogger(__name__)


class ItemList(Component):
    """List selector with cursor and scroll viewport.

    Optional init-only ``header`` / ``footer`` Component slots are fitted chrome
    bands. A slot may define ``chrome_band_height(width, panel_height) -> int``
    (all-or-nothing; default want is 1). Fitted heights live in ``_header_h`` /
    ``_footer_h``. Slots set ``parent`` but are **not** in ``children``. When
    using slots, override :meth:`describe_row`, not :meth:`paint`.
    """

    CURSOR: str = "→"
    # Hint for callers: materialize at most this many rows per viewport refresh when building lists.
    PAGE_SIZE: int = 100
    _DEFAULT_BAND_HEIGHT = 1

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        content: list[str] | None = None,
        on_selection_changed: Callable[[int], None] | None = None,
        *,
        empty_state: list[Segment] | None = None,
        lazy_load: bool = False,
        on_search_changed: Callable[[], None] | None = None,
        id: str | None = None,
        header: Component | None = None,
        footer: Component | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)
        if len(self.CURSOR) > 1:
            raise ComponentError("CURSOR must be a single character")

        self.content = content or [""]

        self._curr_no_sig = Signal(0)
        self._r_start_sig = Signal(0)
        self._unsubs: list[Callable[[], None]] = []
        self._unsubs.append(self._curr_no_sig.subscribe(self._on_curr_no_change))
        self._unsubs.append(self._r_start_sig.subscribe(self._on_r_start_change))
        self._on_change = on_selection_changed
        self._lazy_load = lazy_load
        self._panel_loaded = False
        self.empty_state = empty_state
        # When set, the selector renders multiple rows per item: ``_item_starts[i]``
        # is the row index where item ``i`` begins. ``curr_no`` then tracks the
        # ITEM index, not the row index. ``None`` keeps legacy 1:1 behaviour.
        self._item_starts: list[int] | None = None
        # Content indices that should be skipped during navigation (e.g. separators).
        self._skip_indices: set[int] = set()
        # Filter view: source content and mapping from visible index to source index.
        self._source_content: list[str] = []
        self._filter_fn: Callable[[str, str], bool] | None = None
        self._filter_needle: str = ""
        self._visible_to_source: list[int] = []
        self._search_active: bool = False
        self._search_query: str = ""
        self._on_search_changed = on_search_changed
        self._source_items: list[Any] = []
        self._text_of: Callable[[Any], str] | None = None
        self._header = header
        self._footer = footer
        self._header_h = 0
        self._footer_h = 0
        self._chrome_size: tuple[int, int] | None = None
        if header is not None:
            header.parent = self
        if footer is not None:
            footer.parent = self
        # Slots are owned chrome, not layout children (avoids focus/layout walks).
        self._sync_chrome_bands()

    def _sync_chrome_bands(self) -> None:
        """Recompute fitted band heights from the current ``_size`` if needed."""
        if self._chrome_size == self._size:
            return
        self._chrome_size = self._size
        self._apply_chrome_bands(self._size[0], self._size[1])

    def invalidate_chrome_bands(self) -> None:
        """Force the next sync to refit bands (e.g. after a slot height policy change)."""
        self._chrome_size = None
        self._sync_chrome_bands()

    @staticmethod
    def _slot_want_height(slot: Component, width: int, panel_height: int) -> int:
        """Return how many rows ``slot`` wants; default one row."""
        probe = getattr(slot, "chrome_band_height", None)
        if callable(probe):
            return max(0, int(probe(width, panel_height)))
        return ItemList._DEFAULT_BAND_HEIGHT

    def _apply_chrome_bands(self, width: int, height: int) -> None:
        """Fit chrome into ``height`` (all-or-nothing per slot) and set band heights.

        Header is preferred when both slots compete for remaining space.
        """
        remaining = max(0, height)
        self._header_h = self._fit_slot(self._header, width, height, remaining)
        remaining -= self._header_h
        self._footer_h = self._fit_slot(self._footer, width, height, remaining)

    def _fit_slot(
        self,
        slot: Component | None,
        width: int,
        panel_height: int,
        remaining: int,
    ) -> int:
        """Resize ``slot`` when its full wanted height fits; otherwise height 0."""
        if slot is None or remaining <= 0:
            return 0
        want = self._slot_want_height(slot, width, panel_height)
        if want <= 0 or want > remaining:
            return 0
        slot.resize((width, want))
        return want

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the selector and refresh content if mounted or not lazy."""
        self._size = size
        self._sync_chrome_bands()
        if self._lazy_load:
            if self.is_mounted():
                self.refresh()
                self._panel_loaded = True
            elif not self._panel_loaded:
                self.set_content(["Loading..."])
                self.curr_no = 0
                self._r_start = 0
        else:
            self.refresh()

    @property
    def visible_row_count(self) -> int:
        """List viewport height (panel height minus chrome bands)."""
        self._sync_chrome_bands()
        return max(0, self._size[1] - self._header_h - self._footer_h)

    @property
    def viewport_start(self) -> int:
        """First visible row index (0-based)."""
        return self._r_start

    @property
    def visible_items(self):
        """Content rows in the current scroll window (pagination / virtual window)."""
        return self.content[self._r_start : self._r_start + self.visible_row_count]

    def set_content(self, content: list[str]):
        """Replace the list content and clamp the current selection to the new bounds.

        Resets multi-row item layout — subclasses using :meth:`set_item_starts`
        must call it again after every ``set_content``.
        """
        self.content = content
        self._source_content = list(content)
        self._item_starts = None
        self._visible_to_source = list(range(len(content)))
        if not content:
            self._r_start = 0
            self.curr_no = 0
            self._request_render()
            return
        self.curr_no = min(self.curr_no, len(content) - 1)
        self._scroll_into_view()
        self._request_render()

    def set_source_items(
        self,
        items: Sequence[Any],
        *,
        text_of: Callable[[Any], str],
    ) -> None:
        """Keep ``items``; then ``set_source_content([text_of(x) for x in items])``."""
        self._source_items = list(items)
        self._text_of = text_of
        self.set_source_content([text_of(item) for item in items])

    @property
    def search_active(self) -> bool:
        """True while incremental search mode is active."""
        return self._search_active

    @property
    def search_query(self) -> str:
        """Current search query (may remain after search mode deactivates)."""
        return self._search_query

    def enter_search(self) -> None:
        """Activate search mode, clear the query, and notify listeners."""
        self._search_active = True
        self._search_query = ""
        self._notify_search_changed()

    def search_handle_key(self, key: str) -> bool:
        """Handle search-related key input.

        Returns ``True`` if the key was consumed. When search is inactive,
        always returns ``False`` so ``/`` stays bound via ``@bind_action``.
        """
        if not self._search_active:
            return False
        if key == keys.KEY_ESC:
            self._search_active = False
            self._search_query = ""
            self._notify_search_changed()
            return True
        if key == keys.KEY_ENTER:
            self._search_active = False
            self._notify_search_changed()
            return True
        if key == keys.KEY_BACKSPACE:
            self._search_query = self._search_query[:-1]
            self._notify_search_changed()
            return True
        if len(key) == 1 and key.isprintable():
            self._search_query += key
            self._notify_search_changed()
            return True
        return False

    def _notify_search_changed(self) -> None:
        """Invoke the optional callback and schedule a render."""
        if self._on_search_changed is not None:
            self._on_search_changed()
        self._request_render()

    def _draw_search_bar(self, surface: Surface) -> None:
        """Draw the search/filter bar on the bottom row of ``surface``."""
        if not self._search_query and not self._search_active:
            return
        row = surface.height - 1
        if row < 0:
            return
        theme = get_theme()
        if self._search_active:
            text = f"/{self._search_query}"
            fg = theme.fg_primary
            flags = palette.STYLE_BOLD
        else:
            text = f"filter: {self._search_query}"
            fg = theme.fg_muted
            flags = 0
        text = text.ljust(surface.width)[: surface.width]
        surface.draw_text_rgb(row, 0, text, fg=fg, style_flags=flags)

    def set_source_content(self, content: list[str]) -> None:
        """Set the original unfiltered content.

        Calling this resets any active filter and populates ``content`` with
        the full list.  Use :meth:`set_filter` to apply a substring filter
        afterwards.
        """
        self._filter_needle = ""
        self._visible_to_source = list(range(len(content)))
        self.set_content(content)

    def set_filter(
        self,
        needle: str,
        fn: Callable[[str, str], bool] | None = None,
    ) -> None:
        """Apply a substring filter to the source content.

        Args:
            needle: The search string.  Empty string clears the filter.
            fn: Optional predicate ``fn(row, needle) -> bool``.  Defaults to
                a case-insensitive substring match.
        """
        if needle == self._filter_needle and fn is None:
            return
        self._filter_needle = needle
        if fn is not None:
            self._filter_fn = fn
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Rebuild ``content`` from ``_source_content`` using the current filter."""
        needle = self._filter_needle
        rows = self._source_content
        if not needle.strip():
            filtered = rows
            self._visible_to_source = list(range(len(rows)))
        else:
            fn = self._filter_fn or (lambda row, n: n.lower() in row.lower())
            filtered = []
            visible_to_source = []
            for i, r in enumerate(rows):
                if fn(r, needle):
                    filtered.append(r)
                    visible_to_source.append(i)
            self._visible_to_source = visible_to_source
        self.content = filtered
        self._item_starts = None
        if not filtered:
            self._r_start = 0
            self.curr_no = 0
            return
        self.curr_no = min(self.curr_no, len(filtered) - 1)
        self._scroll_into_view()

    @property
    def source_index(self) -> int:
        """Return the index in the original source content for the current cursor."""
        if not self._visible_to_source:
            return self.curr_no
        return self._visible_to_source[
            min(self.curr_no, len(self._visible_to_source) - 1)
        ]

    def visible_to_source(self, visible_idx: int) -> int:
        """Map a visible (filtered) row index back to the original source index."""
        if not self._visible_to_source:
            return visible_idx
        if visible_idx < 0 or visible_idx >= len(self._visible_to_source):
            return visible_idx
        return self._visible_to_source[visible_idx]

    def set_item_starts(self, starts: Sequence[int] | None) -> None:
        """Switch the selector into multi-row mode.

        ``starts[i]`` is the row index at which item ``i`` begins. The list
        must be ascending and start at 0. Pass ``None`` or an empty sequence
        to revert to 1:1 row-per-item rendering.

        After calling this, :attr:`curr_no` represents the ITEM index;
        :meth:`next` / :meth:`previous` step by items, and the renderer
        uses :meth:`row_to_item` to dispatch sub-rows to ``describe_row``.
        """
        if not starts:
            self._item_starts = None
            return
        self._item_starts = list(starts)
        if self.curr_no >= len(self._item_starts):
            self.curr_no = len(self._item_starts) - 1
        if self.curr_no < 0:
            self.curr_no = 0
        self._scroll_into_view()

    def cursor_row(self) -> int:
        """Return the terminal-row index where the cursor lives."""
        if self._item_starts is None:
            return self.curr_no
        if not self._item_starts:
            return 0
        return self._item_starts[min(self.curr_no, len(self._item_starts) - 1)]

    def row_to_item(self, row: int) -> tuple[int, int]:
        """Translate a row index to ``(item_idx, sub_row)``.

        Falls back to ``(row, 0)`` when not in multi-row mode.
        """
        starts = self._item_starts
        if not starts:
            return row, 0
        # Largest i such that starts[i] <= row.
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= row:
                lo = mid
            else:
                hi = mid - 1
        return lo, row - starts[lo]

    def _scroll_into_view(self) -> None:
        """Adjust ``_r_start`` so the cursor row is visible."""
        row = self.cursor_row()
        visible_h = self.visible_row_count
        if visible_h <= 0:
            return
        if row >= self._r_start + visible_h:
            self._r_start = row - visible_h + 1
        elif row < self._r_start:
            self._r_start = row
        if self._r_start < 0:
            self._r_start = 0

    def set_skip_indices(self, indices: set[int]) -> None:
        """Set content indices that should be skipped during navigation."""
        self._skip_indices = indices

    def _on_curr_no_change(self, _: int) -> None:
        """Handler for _curr_no_sig changes."""
        self._request_render()

    def _on_r_start_change(self, _: int) -> None:
        """Handler for _r_start_sig changes."""
        self._request_render()

    def _request_render(self) -> None:
        """Request a render when mounted and on the visible paint path."""
        mounted = self.is_mounted()
        on_path = is_on_visible_paint_path(self)
        _logger.debug(
            "[RENDER] %s._request_render mounted=%s on_path=%s",
            type(self).__name__,
            mounted,
            on_path,
        )
        if mounted and on_path:
            request_render()

    @property
    def curr_no(self) -> int:
        """Current cursor position (item index)."""
        return self._curr_no_sig.value

    @curr_no.setter
    def curr_no(self, value: int) -> None:
        self._curr_no_sig.set(value)

    @property
    def _r_start(self) -> int:
        """First visible row index (scroll offset)."""
        return self._r_start_sig.value

    @_r_start.setter
    def _r_start(self, value: int) -> None:
        self._r_start_sig.set(value)

    def mount(self) -> None:
        """Activate the list and any chrome slots."""
        super().mount()
        if self._header is not None:
            self._header.mount()
        if self._footer is not None:
            self._footer.mount()

    def unmount(self) -> None:
        """Unmount chrome slots then the list."""
        if self._header is not None:
            self._header.unmount()
        if self._footer is not None:
            self._footer.unmount()
        super().unmount()

    def destroy(self) -> None:
        """Tear down chrome slots, unsubscribe signals, then destroy."""
        if self._header is not None:
            self._header.destroy()
        if self._footer is not None:
            self._footer.destroy()
        for unsub in self._unsubs:
            unsub()
        super().destroy()

    def clear_items(self):
        """Clear the selector content, leaving a single empty item."""
        self.set_content([""])

    def update(self, action, **data):
        """No-op update handler for compatibility with the action system."""

    def paint(self, surface: Surface) -> None:
        """Paint chrome bands, then the list body (rows / empty / search)."""
        self._sync_chrome_bands()
        alloc_w, alloc_h = self._size
        w = min(surface.width, alloc_w)
        h = min(surface.height, alloc_h)
        if w <= 0 or h <= 0:
            return
        # Draw only inside the allocated panel even if ``surface`` is taller.
        panel = (
            surface
            if w == surface.width and h == surface.height
            else surface.subsurface(0, 0, w, h)
        )
        if self._header_h and self._header is not None:
            self._header.paint(panel.subsurface(0, 0, w, self._header_h))
        list_h = min(
            self.visible_row_count, max(0, h - self._header_h - self._footer_h)
        )
        if list_h > 0:
            body = panel.subsurface(self._header_h, 0, w, list_h)
            self._paint_list_body(body)
        if self._footer_h and self._footer is not None:
            self._footer.paint(
                panel.subsurface(self._header_h + list_h, 0, w, self._footer_h)
            )

    def _paint_list_body(self, surface: Surface) -> None:
        """Viewport loop, empty-state, and search bar on the list band only."""
        if not self.content:
            if self.empty_state is not None:
                self._render_empty_state(surface)
            if self._search_query or self._search_active:
                self._draw_search_bar(surface)
            return
        end = min(self._r_start + self.visible_row_count, len(self.content))
        if self._item_starts is None:
            for idx in range(self._r_start, end):
                row = idx - self._r_start
                is_cursor = idx == self.curr_no
                left, main, right = self.describe_row(idx, is_cursor)
                self._draw_row_layout(surface, row, left, main, right)
        else:
            cursor_r = self.cursor_row()
            for idx in range(self._r_start, end):
                row = idx - self._r_start
                is_cursor = idx == cursor_r
                item_idx, sub_row = self.row_to_item(idx)
                left, main, right = self.describe_row(
                    idx, is_cursor, item_idx=item_idx, sub_row=sub_row
                )
                self._draw_row_layout(surface, row, left, main, right)
        if self._search_query or self._search_active:
            self._draw_search_bar(surface)

    def _render_empty_state(self, surface: Surface) -> None:
        """Render empty-state segments centered on the surface."""
        w = surface.width
        h = surface.height
        if w <= 0 or h <= 0:
            return
        lines = self.empty_state
        if lines is None:
            return
        total_height = len(lines)
        start_row = (h - total_height) // 2
        for i, seg in enumerate(lines):
            row = start_row + i
            line_w = wcswidth(seg.text)
            col = max(0, (w - line_w) // 2)
            surface.draw_text_rgb(
                row,
                col,
                seg.text,
                fg=seg.fg,
                bg=seg.bg,
                style_flags=seg.style_flags,
            )

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
        sub_row: int = 0,
    ) -> tuple[
        list[Segment],
        list[Segment] | None,
        list[Segment],
    ]:
        """Return a description of the row at ``idx`` for declarative rendering.

        Subclasses override this to describe what should appear on each row;
        the base class handles all drawing via ``_draw_row_layout``.

        ``item_idx`` and ``sub_row`` are only passed when the panel has
        opted into multi-row layout via :meth:`set_item_starts`. Legacy
        1:1 panels can keep the two-positional-argument signature.

        Returns:
            (left_segments, main_segments, right_segments) where each element
            is a :class:`Segment`.  Main segments are drawn sequentially
            and truncated as a group to fit between left and right;
            ``None`` means no main content.
        """
        return ([Segment(self.content[idx], fg=get_theme().fg_primary)], None, [])

    # --- row-rendering helpers ---

    def _truncate_text(self, text: str, max_width: int) -> str:
        """Truncate text with ellipsis if it exceeds ``max_width`` display columns."""
        if max_width <= 0:
            return ""
        if wcswidth(text) > max_width:
            return truncate_by_width(text, max_width - 1) + "…"
        return text

    def _draw_segments(
        self,
        surface: Surface,
        row: int,
        col: int,
        segments: Sequence[Segment],
    ) -> int:
        """Draw a sequence of segments starting at ``col``.

        Returns the column position after the last segment.
        """
        return surface.draw_segments(row, col, segments)

    def _draw_row_layout(
        self,
        surface: Surface,
        row: int,
        left: Sequence[Segment],
        main: Sequence[Segment] | None,
        right: Sequence[Segment],
        *,
        min_gap: int = 1,
    ) -> None:
        """Draw a row with left segments, main segments, and right-aligned segments.

        Main segments are drawn sequentially after left segments and are truncated
        as a group to fit before right segments, with ``min_gap`` columns of
        minimum spacing on each side.  If the row is too narrow for right
        segments, they are omitted and main is truncated against left only.
        """
        w = surface.width
        left_w = sum(wcswidth(seg.text) for seg in left)
        right_w = sum(wcswidth(seg.text) for seg in right)

        # If any segment declares a background, pre-fill the whole row so
        # gaps between left / main / right and trailing space look uniform.
        row_bg = None
        for seg in list(left) + list(main or []) + list(right):
            if seg.bg is not None:
                row_bg = seg.bg
                break
        if row_bg is not None:
            theme = get_theme()
            surface.draw_text_rgb(row, 0, " " * w, fg=theme.fg_primary, bg=row_bg)

        # Determine how much room main has; drop right if necessary.
        main_avail = w - left_w - right_w - min_gap * 2
        if main_avail < 0 and right:
            right_w = 0
            main_avail = w - left_w - min_gap * 2
        if main_avail < 0:
            main_avail = max(0, w - left_w - min_gap)

        # Draw left segments (truncated if they exceed surface width).
        col = 0
        for seg in left:
            text = seg.text
            text_w = wcswidth(text)
            if col + text_w > w:
                text = self._truncate_text(text, max(0, w - col))
                text_w = wcswidth(text) if text else 0
            if not text:
                break
            surface.draw_text_rgb(
                row,
                col,
                text,
                fg=seg.fg,
                bg=seg.bg,
                style_flags=seg.style_flags,
            )
            col += text_w

        # Draw main segments (truncated as a group to fit).
        if main and main_avail > 0:
            col += min_gap
            remaining = main_avail
            for seg in main:
                text = seg.text
                text_w = wcswidth(text)
                if text_w > remaining:
                    text = self._truncate_text(text, remaining)
                    text_w = wcswidth(text) if text else 0
                if text:
                    surface.draw_text_rgb(
                        row,
                        col,
                        text,
                        fg=seg.fg,
                        bg=seg.bg,
                        style_flags=seg.style_flags,
                    )
                    col += text_w
                remaining -= text_w
                if remaining <= 0:
                    break

        # Draw right segments (right-aligned).
        if right:
            right_start = w - right_w
            if right_start >= left_w + min_gap:
                surface.draw_segments(row, right_start, right)

    def _draw_right_aligned(
        self,
        surface: Surface,
        row: int,
        text: str,
        fg: tuple[int, int, int],
        *,
        style_flags: int = 0,
        margin: int = 4,
    ) -> bool:
        """Draw ``text`` right-aligned if it fits within ``width - margin``.

        Returns ``True`` if drawn, ``False`` if skipped (too wide).
        """
        w = surface.width
        text_w = wcswidth(text)
        if text_w < w - margin:
            surface.draw_text_rgb(
                row,
                w - text_w,
                text,
                fg=fg,
                bg=get_theme().bg_chrome,
                style_flags=style_flags,
            )
            return True
        return False

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change(self.curr_no)
        else:
            self.emit(EVT_SELECTION_CHANGED, index=self.curr_no)

    def next(self, step: int = 1):
        """Move the selection forward by the given step, skipping separators."""
        n_total = (
            len(self._item_starts)
            if self._item_starts is not None
            else len(self.content)
        )
        tmp_no = self.curr_no + step
        while 0 <= tmp_no < n_total and tmp_no in self._skip_indices:
            tmp_no += 1
        if tmp_no < 0 or tmp_no >= n_total:
            return
        self.curr_no = tmp_no
        self._scroll_into_view()
        self._notify_change()

    def previous(self, step: int = 1):
        """Move the selection backward by the given step, skipping separators."""
        n_total = (
            len(self._item_starts)
            if self._item_starts is not None
            else len(self.content)
        )
        tmp_no = self.curr_no - step
        while 0 <= tmp_no < n_total and tmp_no in self._skip_indices:
            tmp_no -= 1
        if tmp_no < 0:
            return
        self.curr_no = tmp_no
        self._scroll_into_view()
        self._notify_change()

    def _select_row(self, item_index: int) -> None:
        """Select ``item_index`` (clamped) and notify listeners."""
        n_total = (
            len(self._item_starts)
            if self._item_starts is not None
            else len(self.content)
        )
        if item_index < 0 or item_index >= n_total:
            return
        self.curr_no = item_index
        self._scroll_into_view()
        self._notify_change()

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Handle click/wheel; chrome bands get first chance, then list scroll/select."""
        self._sync_chrome_bands()
        if event.kind is not MouseKind.PRESS:
            return False
        row0 = event.row - 1
        list_h = self.visible_row_count
        in_header = bool(self._header_h and row0 < self._header_h)
        in_footer = bool(self._footer_h and row0 >= self._header_h + list_h)

        if event.button in (
            MouseButton.WHEEL_UP,
            MouseButton.WHEEL_DOWN,
            MouseButton.WHEEL_LEFT,
            MouseButton.WHEEL_RIGHT,
        ):
            if in_header and self._header is not None:
                if self._header.handle_mouse(event):
                    return True
            if in_footer and self._footer is not None:
                local = self._mouse_with_row(
                    event, event.row - (self._header_h + list_h)
                )
                if self._footer.handle_mouse(local):
                    return True
            if event.button is MouseButton.WHEEL_UP:
                self.previous()
                return True
            if event.button is MouseButton.WHEEL_DOWN:
                self.next()
                return True
            return False

        if event.button is not MouseButton.LEFT:
            return False
        if in_header:
            if self._header is not None:
                self._header.handle_mouse(event)
            return True
        if in_footer:
            if self._footer is not None:
                self._footer.handle_mouse(
                    self._mouse_with_row(event, event.row - (self._header_h + list_h))
                )
            return True
        if row0 < self._header_h or row0 >= self._header_h + list_h:
            return False
        return self._handle_mouse_list(
            self._mouse_with_row(event, event.row - self._header_h)
        )

    @staticmethod
    def _mouse_with_row(event: MouseEvent, row: int) -> MouseEvent:
        """Copy ``event`` with a remapped 1-based row."""
        return MouseEvent(
            col=event.col,
            row=row,
            button=event.button,
            kind=event.kind,
            shift=event.shift,
            alt=event.alt,
            ctrl=event.ctrl,
            motion=event.motion,
        )

    def _handle_mouse_list(self, event: MouseEvent) -> bool:
        """Select a row from list-local mouse coordinates."""
        row0 = event.row - 1
        if row0 < 0 or row0 >= self.visible_row_count:
            return False
        content_index = self._r_start + row0
        if content_index >= len(self.content):
            return False
        if self._item_starts is not None:
            item_index, _sub = self.row_to_item(content_index)
        else:
            item_index = content_index
        if item_index in self._skip_indices:
            return False
        self._select_row(item_index)
        return True
