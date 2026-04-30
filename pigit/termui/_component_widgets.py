# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_component_widgets.py
Description: Widget components for the TUI framework: LineTextBrowser and ItemSelector.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional, Sequence, Union

from . import keys, palette
from ._component_base import Component, ComponentError
from ._segment import Segment
from ._surface import Surface
from ._reactive import Signal
from .types import OverlayDispatchResult
from .tty_io import truncate_line
from .wcwidth_table import pad_by_width
from .wcwidth_table import truncate_by_width, wcswidth

if TYPE_CHECKING:
    pass


class LineTextBrowser(Component):
    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        content: Optional[list[str]] = None,
    ) -> None:
        super().__init__(x, y, size)

        self._content = content
        self._max_line = self._size[1]

        self._i = 0

        self._r = [0, self._size[1]]

    def resize(self, size: tuple[int, int]):
        """Resize the browser and update the maximum visible lines."""
        self._max_line = size[1]
        super().resize(size)

    def _render_surface(self, surface: "Surface") -> None:
        if self._content is None:
            return
        end = min(self._i + self._max_line, len(self._content))
        for idx in range(self._i, end):
            surface.draw_text_rgb(
                idx - self._i,
                0,
                self._content[idx],
                fg=palette.DEFAULT_FG,
                bg=palette.DEFAULT_BG,
            )

    def scroll_up(self, line: int = 1):
        """Scroll the view up by the given number of lines."""
        self._i = max(self._i - line, 0)

    def scroll_down(self, line: int = 1):
        """Scroll the view down by the given number of lines."""
        self._i = min(self._i + line, max(0, len(self._content) - self._max_line))


class ItemSelector(Component):
    CURSOR: str = "\u2192"
    # Hint for callers: materialize at most this many rows per viewport refresh when building lists.
    PAGE_SIZE: int = 100

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        content: Optional[list[str]] = None,
        on_selection_changed: Optional[Callable[[int], None]] = None,
        *,
        lazy_load: bool = False,
    ) -> None:
        super().__init__(x, y, size)

        if len(self.CURSOR) > 1:
            raise ComponentError("CURSOR must be a single character")

        self.content = content or [""]

        self.curr_no = 0
        self._r_start = 0
        self._on_change = on_selection_changed
        self._lazy_load = lazy_load
        self._panel_loaded = False

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
        """Replace the list content and clamp the current selection to the new bounds."""
        self.content = content
        if not content:
            self._r_start = 0
            self.curr_no = 0
            return
        self.curr_no = min(self.curr_no, len(content) - 1)
        visible_h = self._size[1]
        if self.curr_no >= self._r_start + visible_h:
            self._r_start = max(0, self.curr_no - visible_h + 1)
        elif self.curr_no < self._r_start:
            self._r_start = self.curr_no

    def clear_items(self):
        """Clear the selector content, leaving a single empty item."""
        self.set_content([""])

    def update(self, action, **data):
        """No-op update handler for compatibility with the action system."""
        pass

    def _render_surface(self, surface: "Surface") -> None:
        """Viewport loop — delegates to describe_row for each visible item."""
        if not self.content:
            return
        end = min(self._r_start + self._size[1], len(self.content))
        for idx in range(self._r_start, end):
            row = idx - self._r_start
            is_cursor = idx == self.curr_no
            left, main, right = self.describe_row(idx, is_cursor)
            self._draw_row_layout(surface, row, left, main, right)

    def describe_row(self, idx: int, is_cursor: bool) -> tuple[
        list[Segment],
        list[Segment] | None,
        list[Segment],
    ]:
        """Return a description of the row at ``idx`` for declarative rendering.

        Subclasses override this to describe what should appear on each row;
        the base class handles all drawing via ``_draw_row_layout``.

        Returns:
            (left_segments, main_segments, right_segments) where each element
            is a :class:`Segment`.  Main segments are drawn sequentially
            and truncated as a group to fit between left and right;
            ``None`` means no main content.
        """
        prefix = self.CURSOR if is_cursor else " "
        text = f"{prefix}{self.content[idx]}"
        return ([Segment(text, fg=palette.DEFAULT_FG)], None, [])

    # --- row-rendering helpers ---

    def _truncate_text(self, text: str, max_width: int) -> str:
        """Truncate text with ellipsis if it exceeds ``max_width`` display columns."""
        if max_width <= 0:
            return ""
        if wcswidth(text) > max_width:
            return truncate_by_width(text, max_width - 1) + "\u2026"
        return text

    def _draw_segments(
        self,
        surface: "Surface",
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
        surface: "Surface",
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
        surface: "Surface",
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

    def next(self, step: int = 1):
        """Move the selection forward by the given step."""
        tmp_no = self.curr_no + step
        if tmp_no < 0 or tmp_no >= len(self.content):
            return

        self.curr_no += step
        if self.curr_no >= self._r_start + self._size[1]:
            self._r_start += step
        self._notify_change()

    def previous(self, step: int = 1):
        """Move the selection backward by the given step."""
        tmp = self.curr_no - step
        if tmp < 0:
            return

        self.curr_no -= step
        if self.curr_no < self._r_start:
            self._r_start -= step
        self._notify_change()


class Header(Component):
    """Generic header bar with left/center/right segments.

    Each slot is a sequence of :class:`Segment`.  Center is
    horizontally centred; right is right-aligned.  If the total width
    exceeds the available space, the centre group is dropped first, then
    the left group is truncated with an ellipsis.
    """

    def __init__(
        self,
        *,
        separator: bool = True,
        sep_fg: tuple[int, int, int] = (100, 100, 100),
        on_refresh: Optional[Callable[["Header"], None]] = None,
    ) -> None:
        super().__init__()
        self._separator = separator
        self._sep_fg = sep_fg
        self._on_refresh = on_refresh
        self._left: list[Segment] = []
        self._center: list[Segment] = []
        self._right: list[Segment] = []

    def set_left(self, segments: Sequence[Segment]) -> None:
        """Set the left header segments."""
        self._left = list(segments)

    def set_center(self, segments: Sequence[Segment]) -> None:
        """Set the center header segments."""
        self._center = list(segments)

    def set_right(self, segments: Sequence[Segment]) -> None:
        """Set the right header segments."""
        self._right = list(segments)

    def _render_surface(self, surface: "Surface") -> None:
        if self._on_refresh is not None:
            self._on_refresh(self)

        w = surface.width
        h = surface.height
        if w <= 0:
            return

        if h >= 2 and self._separator:
            self._draw_content(surface, 0, w)
            surface.fill_rect_rgb(1, 0, w, 1, palette.DEFAULT_BG)
            surface.draw_text_rgb(
                1, 0, "\u2500" * w, fg=self._sep_fg, bg=palette.DEFAULT_BG
            )
        else:
            self._draw_content(surface, 0, w)

    def _draw_content(self, surface: "Surface", row: int, w: int) -> None:
        surface.fill_rect_rgb(row, 0, w, 1, palette.DEFAULT_BG)

        left_w = self._slot_width(self._left)
        center_w = self._slot_width(self._center)
        right_w = self._slot_width(self._right)

        # Drop centre if total exceeds width
        total = left_w + (2 if center_w else 0) + center_w + right_w
        if total > w and center_w:
            center_w = 0
            total = left_w + right_w

        # Truncate left if still exceeds
        if total > w:
            max_left = max(0, w - right_w - 1)
            self._left = self._truncate_slot(self._left, max_left)
            left_w = self._slot_width(self._left)

        # Draw left
        x = 0
        for seg in self._left:
            surface.draw_text_rgb(
                row,
                x,
                seg.text,
                fg=seg.fg,
                bg=seg.bg,
                style_flags=seg.style_flags,
            )
            x += wcswidth(seg.text)

        # Draw centre
        if self._center and center_w:
            centre_x = max(0, (w - center_w) // 2)
            x = centre_x
            for seg in self._center:
                surface.draw_text_rgb(
                    row,
                    x,
                    seg.text,
                    fg=seg.fg,
                    bg=seg.bg,
                    style_flags=seg.style_flags,
                )
                x += wcswidth(seg.text)

        # Draw right
        if self._right and right_w:
            right_x = max(0, w - right_w)
            x = right_x
            for seg in self._right:
                surface.draw_text_rgb(
                    row,
                    x,
                    seg.text,
                    fg=seg.fg,
                    bg=seg.bg,
                    style_flags=seg.style_flags,
                )
                x += wcswidth(seg.text)

    @staticmethod
    def _slot_width(slot: Sequence[Segment]) -> int:
        return sum(wcswidth(seg.text) for seg in slot)

    @staticmethod
    def _truncate_slot(slot: Sequence[Segment], max_width: int) -> list[Segment]:
        if max_width <= 0 or not slot:
            return []
        result: list[Segment] = []
        current_w = 0
        for seg in slot:
            text_w = wcswidth(seg.text)
            if current_w + text_w > max_width - 1:
                avail = max_width - current_w - 1
                if avail > 0:
                    truncated = truncate_by_width(seg.text, avail) + "\u2026"
                    result.append(
                        Segment(
                            truncated, fg=seg.fg, bg=seg.bg, style_flags=seg.style_flags
                        )
                    )
                break
            result.append(seg)
            current_w += text_w
        return result


class StatusBar(Component):
    """Single-line status bar.

    When placed inside a layout container (e.g. ``Column``), ``x`` and ``y``
    are managed by the container and manual values are ignored.
    """

    def __init__(
        self,
        text: Union[str, Signal[str]] = "",
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size)
        self._unsub: Optional[Callable[[], None]] = None
        if isinstance(text, Signal):
            self._text = text.value
            self._unsub = text.subscribe(self._on_change)
        else:
            self._text = text

    def set_text(self, text: str) -> None:
        """Update the displayed status text."""
        self._text = text

    def _on_change(self, text: str) -> None:
        self._text = text

    def destroy(self) -> None:
        """Unsubscribe from the signal and clean up resources."""
        if self._unsub:
            self._unsub()

    def _render_surface(self, surface: "Surface") -> None:
        text = truncate_line(self._text, surface.width)
        text = pad_by_width(text, surface.width)
        surface.draw_text_rgb(0, 0, text, fg=palette.DEFAULT_FG, bg=palette.DEFAULT_BG)


class InputLine(Component):
    """Single-line text input.

    ``max_length`` limits Unicode code points (not display width).
    When placed inside a layout container (e.g. ``Column``), ``x`` and ``y``
    are managed by the container and manual values are ignored.
    """

    def __init__(
        self,
        prompt: str = "",
        visible: bool = True,
        max_length: Optional[int] = None,
        on_value_changed: Optional[Callable[[str], None]] = None,
        on_submit: Optional[Callable[[str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        candidate_provider: Optional[Callable[[str], list[str]]] = None,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size)
        self._prompt = prompt
        self._visible = visible
        self._max_length = max_length
        self._on_change = on_value_changed
        self._on_submit = on_submit
        self._on_cancel = on_cancel
        self._value = ""
        self._cursor = 0
        # Completion state
        self._candidate_provider = candidate_provider
        self._candidates: list[str] = []
        self._candidate_idx = 0
        self._showing_candidates = False
        self._original_value = ""

    @property
    def value(self) -> str:
        """Return the current input value."""
        return self._value

    @property
    def cursor(self) -> int:
        """Return the current cursor position."""
        return self._cursor

    @property
    def prompt(self) -> str:
        """Return the current prompt text."""
        return self._prompt

    def set_value(self, text: str) -> None:
        """Replace current value and move cursor to end."""
        if self._max_length:
            text = text[: self._max_length]
        if self._value == text:
            return
        self._value = text
        self._cursor = len(self._value)
        if self._on_change:
            self._on_change(self._value)

    def set_visible(self, visible: bool) -> None:
        """Toggle whether the input line is visible."""
        self._visible = visible

    def insert(self, ch: str) -> None:
        """Insert a character at the current cursor position."""
        if self._max_length and len(self._value) >= self._max_length:
            return
        self._value = self._value[: self._cursor] + ch + self._value[self._cursor :]
        self._cursor += 1
        if self._on_change:
            self._on_change(self._value)

    def delete(self) -> None:
        """Delete character after cursor."""
        if self._cursor < len(self._value):
            self._value = self._value[: self._cursor] + self._value[self._cursor + 1 :]
            if self._on_change:
                self._on_change(self._value)

    def backspace(self) -> None:
        """Delete the character before the cursor."""
        if self._cursor > 0:
            self._value = self._value[: self._cursor - 1] + self._value[self._cursor :]
            self._cursor -= 1
            if self._on_change:
                self._on_change(self._value)

    def home(self) -> None:
        """Move cursor to start of line."""
        self._cursor = 0

    def end(self) -> None:
        """Move cursor to end of line."""
        self._cursor = len(self._value)

    def clear(self) -> None:
        """Clear the input value and reset the cursor."""
        self._value = ""
        self._cursor = 0
        if self._on_change:
            self._on_change(self._value)

    def set_prompt(self, prompt: str) -> None:
        """Switch prompt text at runtime."""
        self._prompt = prompt

    def set_candidate_provider(
        self, provider: Optional[Callable[[str], list[str]]]
    ) -> None:
        """Switch or clear the candidate provider at runtime.

        When ``provider`` is *None*, the *Tab* key behaves as a plain key.
        """
        self._candidate_provider = provider
        self._candidates = []
        self._candidate_idx = 0
        self._showing_candidates = False

    def on_key(self, key: str) -> None:
        """Process keyboard input for this input line.

        Callers (e.g. ``Application`` subclasses) are responsible for
        ensuring this method is only invoked when the input line is active.
        """
        if key == keys.KEY_ENTER:
            if self._showing_candidates:
                self._value = self._candidates[self._candidate_idx]
                self._cursor = len(self._value)
                self._showing_candidates = False
                self._candidates = []
                return
            if self._on_submit:
                self._on_submit(self._value)
            return

        if key == keys.KEY_ESC:
            if self._showing_candidates:
                self._value = self._original_value
                self._cursor = len(self._value)
                self._showing_candidates = False
                self._candidates = []
                return
            if self._on_cancel:
                self._on_cancel()
            return

        if key in (keys.KEY_TAB, keys.KEY_SHIFT_TAB) and self._candidate_provider:
            if not self._showing_candidates:
                self._showing_candidates = True
                self._original_value = self._value
                self._candidates = self._candidate_provider(self._value)
                self._candidate_idx = 0
            else:
                step = 1 if key == keys.KEY_TAB else -1
                self._candidate_idx = max(
                    0, min(self._candidate_idx + step, len(self._candidates) - 1)
                )
            if self._candidates:
                self._value = self._candidates[self._candidate_idx]
                self._cursor = len(self._value)
            return

        if key in (keys.KEY_UP, keys.KEY_DOWN) and self._showing_candidates:
            step = -1 if key == keys.KEY_UP else 1
            self._candidate_idx = max(
                0, min(self._candidate_idx + step, len(self._candidates) - 1)
            )
            self._value = self._candidates[self._candidate_idx]
            self._cursor = len(self._value)
            return

        # Plain text editing
        if key == keys.KEY_BACKSPACE:
            self.backspace()
        elif key == keys.KEY_DELETE:
            self.delete()
        elif key == keys.KEY_LEFT:
            self.cursor_left()
        elif key == keys.KEY_RIGHT:
            self.cursor_right()
        elif key == keys.KEY_HOME:
            self.home()
        elif key == keys.KEY_END:
            self.end()
        elif len(key) == 1 and key.isprintable() and ord(key) >= 32:
            self.insert(key)

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        """Route keys to this input line when it is inside an overlay (Sheet/Popup)."""
        self.on_key(key)
        return OverlayDispatchResult.HANDLED_EXPLICIT

    def cursor_left(self) -> None:
        """Move the cursor one position to the left."""
        self._cursor = max(0, self._cursor - 1)

    def cursor_right(self) -> None:
        """Move the cursor one position to the right."""
        self._cursor = min(len(self._value), self._cursor + 1)

    def _render_surface(self, surface: "Surface") -> None:
        if not self._visible:
            return
        core = f"{self._prompt}{self._value}"
        prompt_len = len(self._prompt)
        cursor_abs = prompt_len + self._cursor

        if self._showing_candidates and self._candidates:
            # Inline completion: text already typed by the user stays normal,
            # the rest of the candidate is shown dim.
            match_len = len(self._original_value)
            matched = self._value[:match_len]
            suffix = self._value[match_len:]
            prefix = f"{self._prompt}{matched}"
            avail = surface.width - len(prefix)
            if avail < 0:
                prefix = prefix[: surface.width - 1] + "…" if surface.width > 0 else ""
                suffix = ""
            elif len(suffix) > avail:
                suffix = suffix[:avail]
            surface.draw_text_rgb(
                0, 0, prefix, fg=palette.DEFAULT_FG, bg=palette.DEFAULT_BG
            )
            if suffix:
                surface.draw_text_rgb(
                    0,
                    len(prefix),
                    suffix,
                    fg=palette.DEFAULT_FG_DIM,
                    bg=palette.DEFAULT_BG,
                )
            # Block cursor at the end of the completion text.
            cursor_abs = len(prefix) + len(suffix)
            if cursor_abs < surface.width:
                surface.draw_text_rgb(
                    0, cursor_abs, " ", fg=palette.DEFAULT_BG, bg=palette.DEFAULT_FG
                )
        else:
            text = truncate_line(core, surface.width)
            text = pad_by_width(text, surface.width)
            surface.draw_text_rgb(
                0, 0, text, fg=palette.DEFAULT_FG, bg=palette.DEFAULT_BG
            )
            # Draw block cursor (reverse video) over the character at cursor.
            if cursor_abs < surface.width:
                if self._cursor < len(self._value):
                    ch = self._value[self._cursor]
                else:
                    ch = " "
                surface.draw_text_rgb(
                    0, cursor_abs, ch, fg=palette.DEFAULT_BG, bg=palette.DEFAULT_FG
                )
