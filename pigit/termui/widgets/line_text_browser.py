"""
Module: pigit/termui/widgets/line_text_browser.py
Description: Simple scrollable text browser widget.
Author: Zev
Date: 2026-05-16
"""

from __future__ import annotations

from ..component import Component
from ..mouse import MouseButton, MouseKind, MouseEvent
from ..segment import Segment
from ..surface import Surface, _Subsurface
from ..theme import get_theme

_USE_THEME_BG = object()


class LineTextBrowser(Component):
    WHEEL_SCROLL_LINES = 1

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        content: list[str] | list[list[Segment]] | None = None,
        id: str | None = None,
        bg: tuple[int, int, int] | None = _USE_THEME_BG,
    ) -> None:
        super().__init__(x, y, size, id=id)
        self._rows: list[list[Segment]] | None = None
        self._content: list[str] | None
        self._max_line = self._size[1]
        self._bg = bg
        self._i = 0
        self._r = [0, self._size[1]]
        if content is None:
            self._content = None
        elif content and isinstance(content[0], list):
            rows = content
            self._rows = rows
            self._content = ["".join(seg.text for seg in row) for row in rows]
        else:
            self._content = content

    def resize(self, size: tuple[int, int]):
        """Resize the browser and update the maximum visible lines."""
        self._max_line = size[1]
        super().resize(size)

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        rows = self._visible_rows()
        if rows is None:
            return
        end = min(self._i + self._max_line, len(rows))
        for idx in range(self._i, end):
            surface.draw_segments(idx - self._i, 0, rows[idx])

    def _visible_rows(self) -> list[list[Segment]] | None:
        if self._rows is not None:
            return self._rows
        if self._content is None:
            return None
        theme = get_theme()
        fg = theme.fg_primary
        row_bg = theme.bg_chrome if self._bg is _USE_THEME_BG else self._bg
        return [[Segment(line, fg=fg, bg=row_bg)] for line in self._content]

    def scroll_up(self, line: int = 1):
        """Scroll the view up by the given number of lines."""
        self._i = max(self._i - line, 0)

    def scroll_down(self, line: int = 1):
        """Scroll the view down by the given number of lines."""
        if not self._content:
            return
        self._i = min(self._i + line, max(0, len(self._content) - self._max_line))

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Scroll on wheel; one detent scrolls ``WHEEL_SCROLL_LINES`` lines."""
        if event.kind is not MouseKind.PRESS:
            return False
        if event.button is MouseButton.WHEEL_UP:
            self.scroll_up(self.WHEEL_SCROLL_LINES)
            return True
        if event.button is MouseButton.WHEEL_DOWN:
            self.scroll_down(self.WHEEL_SCROLL_LINES)
            return True
        return False
