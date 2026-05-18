"""
Module: pigit/termui/widgets/line_text_browser.py
Description: Simple scrollable text browser widget.
Author: Zev
Date: 2026-05-16
"""

from __future__ import annotations

from .. import palette
from .._component import Component
from .._surface import Surface, _Subsurface


class LineTextBrowser(Component):
    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        content: list[str] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)
        self._content = content
        self._max_line = self._size[1]

        self._i = 0

        self._r = [0, self._size[1]]

    def resize(self, size: tuple[int, int]):
        """Resize the browser and update the maximum visible lines."""
        self._max_line = size[1]
        super().resize(size)

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
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
        if not self._content:
            return
        self._i = min(self._i + line, max(0, len(self._content) - self._max_line))
