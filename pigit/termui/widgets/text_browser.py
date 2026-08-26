"""
Module: pigit/termui/widgets/text_browser.py
Description: Scrollable text browser for plain or segment rows.
Author: Zev
Date: 2026-05-16
"""

from __future__ import annotations

from ..component import Component
from ..mouse import MouseButton, MouseKind, MouseEvent
from ..segment import Segment
from ..surface import Surface
from ..theme import get_theme


class _ThemeBg:
    """Sentinel: paint plain lines with ``theme.bg_chrome``."""

    __slots__ = ()


_USE_THEME_BG = _ThemeBg()


class TextBrowser(Component):
    """Scrollable browser for plain strings or pre-styled segment rows."""

    WHEEL_SCROLL_LINES = 1

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        content: list[str] | list[list[Segment]] | None = None,
        id: str | None = None,
        bg: tuple[int, int, int] | None | _ThemeBg = _USE_THEME_BG,
    ) -> None:
        super().__init__(x, y, size, id=id)
        self._rows: list[list[Segment]] | None = None
        self._content: list[str] = []
        self._max_line = self._size[1]
        self._bg = bg
        self._i = 0
        self._r = [0, self._size[1]]
        # Cached segment form of string content (rebuilt only when the theme
        # colors change), so each render does not re-allocate a Segment per line.
        self._cache_fg: tuple[int, int, int] | None = None
        self._cache_bg: tuple[int, int, int] | None = None
        self._cache_rows: list[list[Segment]] | None = None
        if content is None:
            return
        if content and isinstance(content[0], list):
            rows: list[list[Segment]] = []
            for row in content:
                if not isinstance(row, list):
                    raise TypeError("mixed plain/segment content is not supported")
                rows.append(row)
            self.set_segment_rows(rows)
            return
        lines: list[str] = []
        for line in content:
            if not isinstance(line, str):
                raise TypeError("mixed plain/segment content is not supported")
            lines.append(line)
        self.set_plain_lines(lines)

    def _clamp_scroll_i(self, value: int) -> int:
        """Clamp scroll index to ``[0, max(0, len(lines) - viewport_rows)]``."""
        max_i = max(0, len(self._content) - self._max_line)
        return max(0, min(int(value), max_i))

    @property
    def lines(self) -> list[str]:
        """Plain-text lines (segment rows contribute joined text)."""
        return self._content

    @property
    def scroll_i(self) -> int:
        """First visible line index (clamped to viewport)."""
        return self._i

    @scroll_i.setter
    def scroll_i(self, value: int) -> None:
        self._i = self._clamp_scroll_i(value)

    @property
    def viewport_rows(self) -> int:
        """How many lines fit in the current size."""
        return self._max_line

    def replace_lines(
        self,
        lines: list[str],
        *,
        scroll_i: int | None = None,
    ) -> None:
        """Replace plain lines; default scroll 0; optional restore then clamp."""
        self._rows = None
        self._content = list(lines)
        self._cache_rows = None
        self._i = self._clamp_scroll_i(0 if scroll_i is None else scroll_i)

    def set_plain_lines(self, lines: list[str]) -> None:
        """Replace content with plain strings; clear any segment-row override."""
        self.replace_lines(lines)

    def set_segment_rows(self, rows: list[list[Segment]]) -> None:
        """Replace content with pre-styled segment rows."""
        self._rows = rows
        self._content = ["".join(seg.text for seg in row) for row in rows]
        self._cache_rows = None
        self._i = self._clamp_scroll_i(0)

    def resize(self, size: tuple[int, int]):
        """Resize the browser and update the maximum visible lines."""
        self._max_line = size[1]
        super().resize(size)

    def paint(self, surface: Surface) -> None:
        rows = self._visible_rows()
        if rows is None:
            return
        end = min(self._i + self._max_line, len(rows))
        for idx in range(self._i, end):
            surface.draw_segments(idx - self._i, 0, rows[idx])

    def _visible_rows(self) -> list[list[Segment]] | None:
        if self._rows is not None:
            return self._rows
        if not self._content:
            return None
        theme = get_theme()
        fg = theme.fg_primary
        row_bg = theme.bg_chrome if isinstance(self._bg, _ThemeBg) else self._bg
        if self._cache_rows is None or (self._cache_fg, self._cache_bg) != (fg, row_bg):
            self._cache_fg, self._cache_bg = fg, row_bg
            self._cache_rows = [
                [Segment(line, fg=fg, bg=row_bg)] for line in self._content
            ]
        return self._cache_rows

    def scroll_up(self, line: int = 1):
        """Scroll the view up by the given number of lines."""
        self._i = max(0, self._i - line)

    def scroll_down(self, line: int = 1):
        """Scroll the view down by the given number of lines."""
        if not self._content:
            return
        self._i = self._clamp_scroll_i(self._i + line)

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
