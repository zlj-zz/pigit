# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_component_widgets.py
Description: Widget components for the TUI framework: LineTextBrowser and ItemSelector.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional, Union

from ._component_base import Component, ComponentError
from ._reactive import Signal
from .keys import (
    KEY_BACKSPACE,
    KEY_DELETE,
    KEY_END,
    KEY_ENTER,
    KEY_ESC,
    KEY_HOME,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_SHIFT_TAB,
    KEY_TAB,
    KEY_UP,
    KEY_DOWN,
)
from .tty_io import truncate_line

if TYPE_CHECKING:
    from ._surface import Surface


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
        self._max_line = size[1]
        super().resize(size)

    def _render_surface(self, surface: "Surface") -> None:
        if self._content is None:
            return
        end = min(self._i + self._max_line, len(self._content))
        for idx in range(self._i, end):
            surface.draw_text(idx - self._i, 0, self._content[idx])

    def scroll_up(self, line: int = 1):
        self._i = max(self._i - line, 0)

    def scroll_down(self, line: int = 1):
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
    ) -> None:
        super().__init__(x, y, size)

        if len(self.CURSOR) > 1:
            raise ComponentError("error")

        self.content = content or [""]

        self.curr_no = 0
        self._r_start = 0
        self._on_change = on_selection_changed

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
        self.set_content([""])

    def update(self, action, **data):
        pass

    def _render_surface(self, surface: "Surface") -> None:
        if not self.content:
            return
        end = min(self._r_start + self._size[1], len(self.content))
        for idx in range(self._r_start, end):
            prefix = self.CURSOR if idx == self.curr_no else " "
            surface.draw_text(idx - self._r_start, 0, f"{prefix}{self.content[idx]}")

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change(self.curr_no)

    def next(self, step: int = 1):
        tmp_no = self.curr_no + step
        if tmp_no < 0 or tmp_no >= len(self.content):
            return

        self.curr_no += step
        if self.curr_no >= self._r_start + self._size[1]:
            self._r_start += step
        self._notify_change()

    def previous(self, step: int = 1):
        tmp = self.curr_no - step
        if tmp < 0 or tmp >= len(self.content):
            return

        self.curr_no -= step
        if self.curr_no < self._r_start:
            self._r_start -= step
        self._notify_change()


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
        self._text = text

    def _on_change(self, text: str) -> None:
        self._text = text

    def destroy(self) -> None:
        if self._unsub:
            self._unsub()

    def _render_surface(self, surface: "Surface") -> None:
        surface.draw_row(0, truncate_line(self._text, surface.width))


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
        return self._value

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
        self._visible = visible

    def insert(self, ch: str) -> None:
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
        if key == KEY_ENTER:
            if self._showing_candidates:
                self._value = self._candidates[self._candidate_idx]
                self._cursor = len(self._value)
                self._showing_candidates = False
                self._candidates = []
                return
            if self._on_submit:
                self._on_submit(self._value)
            return

        if key == KEY_ESC:
            if self._showing_candidates:
                self._value = self._original_value
                self._cursor = len(self._value)
                self._showing_candidates = False
                self._candidates = []
                return
            if self._on_cancel:
                self._on_cancel()
            return

        if key in (KEY_TAB, KEY_SHIFT_TAB) and self._candidate_provider:
            if not self._showing_candidates:
                self._showing_candidates = True
                self._original_value = self._value
                self._candidates = self._candidate_provider(self._value)
                self._candidate_idx = 0
            else:
                step = 1 if key == KEY_TAB else -1
                self._candidate_idx = max(
                    0, min(self._candidate_idx + step, len(self._candidates) - 1)
                )
            if self._candidates:
                self._value = self._candidates[self._candidate_idx]
                self._cursor = len(self._value)
            return

        if key in (KEY_UP, KEY_DOWN) and self._showing_candidates:
            step = -1 if key == KEY_UP else 1
            self._candidate_idx = max(
                0, min(self._candidate_idx + step, len(self._candidates) - 1)
            )
            self._value = self._candidates[self._candidate_idx]
            self._cursor = len(self._value)
            return

        # Plain text editing
        if key == KEY_BACKSPACE:
            self.backspace()
        elif key == KEY_DELETE:
            self.delete()
        elif key == KEY_LEFT:
            self.cursor_left()
        elif key == KEY_RIGHT:
            self.cursor_right()
        elif key == KEY_HOME:
            self.home()
        elif key == KEY_END:
            self.end()
        elif len(key) == 1 and key.isprintable() and ord(key) >= 32:
            self.insert(key)

    def cursor_left(self) -> None:
        self._cursor = max(0, self._cursor - 1)

    def cursor_right(self) -> None:
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
            surface.draw_text(0, 0, prefix)
            if suffix:
                surface.draw_text(0, len(prefix), f"\033[2m{suffix}\033[0m")
            # Block cursor at the end of the completion text.
            cursor_abs = len(prefix) + len(suffix)
            if cursor_abs < surface.width:
                surface.draw_text(0, cursor_abs, "\033[7m \033[0m")
        else:
            surface.draw_row(0, truncate_line(core, surface.width))
            # Draw block cursor (reverse video) over the character at cursor.
            if cursor_abs < surface.width:
                if self._cursor < len(self._value):
                    ch = self._value[self._cursor]
                else:
                    ch = " "
                surface.draw_text(0, cursor_abs, f"\033[7m{ch}\033[0m")
