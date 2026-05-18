"""
Module: pigit/termui/widgets/item_list.py
Description: List selector widget with cursor and scroll viewport.
Author: Zev
Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .. import palette
from .._component import Component, ComponentError
from .._runtime_context import request_render
from .._segment import Segment
from .._surface import Surface, _Subsurface
from ..reactive import Signal, ValueRef
from ..types import ActionEventType
from ..wcwidth_table import truncate_by_width, wcswidth


class ItemList(Component):
    CURSOR: str = "→"
    # Hint for callers: materialize at most this many rows per viewport refresh when building lists.
    PAGE_SIZE: int = 100

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
        id: str | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)
        if len(self.CURSOR) > 1:
            raise ComponentError("CURSOR must be a single character")

        self.content = content or [""]

        self._curr_no_sig = Signal(0)
        self._r_start_sig = Signal(0)
        self._unsubs: list[Callable[[], None]] = []
        self._unsubs.append(
            self._curr_no_sig.subscribe(lambda _: self._request_render())
        )
        self._unsubs.append(
            self._r_start_sig.subscribe(lambda _: self._request_render())
        )
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

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the selector and refresh content if activated or not lazy."""
        self._size = size
        if self._lazy_load:
            if self.is_activated():
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
        """Viewport height in rows (how many list lines are painted per frame)."""
        return self._size[1]

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
            return
        self.curr_no = min(self.curr_no, len(content) - 1)
        self._scroll_into_view()

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
        visible_h = self._size[1]
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

    def _request_render(self) -> None:
        """Request a render if this component is currently activated."""
        if self.is_activated():
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

    def destroy(self) -> None:
        """Unsubscribe from signals and tear down."""
        for unsub in self._unsubs:
            unsub()
        super().destroy()

    def clear_items(self):
        """Clear the selector content, leaving a single empty item."""
        self.set_content([""])

    def update(self, action, **data):
        """No-op update handler for compatibility with the action system."""

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        """Viewport loop — delegates to describe_row for each visible item."""
        if not self.content:
            if self.empty_state is not None:
                self._render_empty_state(surface)
            return
        end = min(self._r_start + self._size[1], len(self.content))
        if self._item_starts is None:
            for idx in range(self._r_start, end):
                row = idx - self._r_start
                is_cursor = idx == self.curr_no
                left, main, right = self.describe_row(idx, is_cursor)
                self._draw_row_layout(surface, row, left, main, right)
            return
        cursor_r = self.cursor_row()
        for idx in range(self._r_start, end):
            row = idx - self._r_start
            is_cursor = idx == cursor_r
            item_idx, sub_row = self.row_to_item(idx)
            left, main, right = self.describe_row(
                idx, is_cursor, item_idx=item_idx, sub_row=sub_row
            )
            self._draw_row_layout(surface, row, left, main, right)

    def _render_empty_state(self, surface: Surface | _Subsurface) -> None:
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
        return ([Segment(self.content[idx], fg=palette.DEFAULT_FG)], None, [])

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
        surface: Surface | _Subsurface,
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
            surface.draw_text_rgb(row, 0, " " * w, fg=palette.DEFAULT_FG, bg=row_bg)

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
                bg=palette.DEFAULT_BG,
                style_flags=style_flags,
            )
            return True
        return False

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change(self.curr_no)
        else:
            self.emit(ActionEventType.selection_changed, index=self.curr_no)

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
