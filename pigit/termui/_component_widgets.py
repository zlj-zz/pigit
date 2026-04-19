# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_component_widgets.py
Description: Widget components for the TUI framework: LineTextBrowser and ItemSelector.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ._component_base import Component, ComponentError

if TYPE_CHECKING:
    from ._renderer import Renderer
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

        self._i = 0  # start display line index of content.

        self._r = [0, self._size[1]]  # display range.

    def resize(self, size: tuple[int, int]):
        self._max_line = size[1]
        super().resize(size)

    def _render_surface(self, surface: "Surface") -> None:
        if self._content is None:
            return
        chunk = self._content[self._i : self._i + self._max_line]
        chunk = chunk[: max(0, self._size[1] - self.x + 1)]
        for idx, line in enumerate(chunk):
            surface.draw_text(idx, 0, line)

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
    ) -> None:
        super().__init__(x, y, size)

        if len(self.CURSOR) > 1:
            raise ComponentError("error")

        self.content = content or [""]
        self.content_len = len(self.content) - 1

        self.curr_no = 0  # default start with 0.
        self._r_start = 0

    @property
    def visible_row_count(self) -> int:
        """Viewport height in rows (how many list lines are painted per frame)."""
        return self._size[1]

    @property
    def visible_items(self):
        """Content rows in the current scroll window (pagination / virtual window)."""
        return self.content[self._r_start : self._r_start + self.visible_row_count]

    def set_content(self, content: list[str]):
        self.content = content
        self.content_len = len(self.content) - 1

    def clear_items(self):
        self.set_content([""])

    def update(self, action, **data):
        pass

    def _render_surface(self, surface: "Surface") -> None:
        if not self.content:
            return
        visible = self.visible_items[: max(0, self._size[1] - self.x + 1)]
        for idx, item in enumerate(visible):
            no = self._r_start + idx
            prefix = self.CURSOR if no == self.curr_no else " "
            surface.draw_text(idx, 0, f"{prefix}{item}")

    def next(self, step: int = 1):
        tmp_no = self.curr_no + step
        if tmp_no < 0 or tmp_no > self.content_len:
            return

        self.curr_no += step
        if self.curr_no >= self._r_start + self._size[1]:
            self._r_start += step

    def forward(self, step: int = 1):
        tmp = self.curr_no - step
        if tmp < 0 or tmp > self.content_len:
            return

        self.curr_no -= step
        if self.curr_no < self._r_start:
            self._r_start -= step
