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
from .tty_io import truncate_line

if TYPE_CHECKING:
    from ._surface import Surface


class LineTextBrowser(Component):
    NAME = "line_text_browser"

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
        chunk = self._content[self._i : self._i + self._max_line]
        for idx, line in enumerate(chunk):
            surface.draw_text(idx, 0, line)

    def scroll_up(self, line: int = 1):
        self._i = max(self._i - line, 0)

    def scroll_down(self, line: int = 1):
        self._i = min(self._i + line, max(0, len(self._content) - self._max_line))


class ItemSelector(Component):
    NAME = "item_selector"
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
        self._r_start = 0

    def clear_items(self):
        self.set_content([""])

    def update(self, action, **data):
        pass

    def _render_surface(self, surface: "Surface") -> None:
        if not self.content:
            return
        visible = self.visible_items
        for idx, item in enumerate(visible):
            no = self._r_start + idx
            prefix = self.CURSOR if no == self.curr_no else " "
            surface.draw_text(idx, 0, f"{prefix}{item}")

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

    def forward(self, step: int = 1):
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

    NAME = "status_bar"

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

    NAME = "input_line"

    def __init__(
        self,
        prompt: str = "",
        visible: bool = True,
        max_length: Optional[int] = None,
        on_value_changed: Optional[Callable[[str], None]] = None,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size)
        self._prompt = prompt
        self._visible = visible
        self._max_length = max_length
        self._on_change = on_value_changed
        self._value = ""
        self._cursor = 0

    @property
    def value(self) -> str:
        return self._value

    def set_value(self, text: str) -> None:
        """Replace current value and move cursor to end."""
        if self._max_length:
            text = text[: self._max_length]
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
            self._value = (
                self._value[: self._cursor] + self._value[self._cursor + 1 :]
            )
            if self._on_change:
                self._on_change(self._value)

    def backspace(self) -> None:
        if self._cursor > 0:
            self._value = (
                self._value[: self._cursor - 1] + self._value[self._cursor :]
            )
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

    def cursor_left(self) -> None:
        self._cursor = max(0, self._cursor - 1)

    def cursor_right(self) -> None:
        self._cursor = min(len(self._value), self._cursor + 1)

    def _render_surface(self, surface: "Surface") -> None:
        if not self._visible:
            return
        line = f"{self._prompt}{self._value}"
        surface.draw_row(0, truncate_line(line, surface.width))


