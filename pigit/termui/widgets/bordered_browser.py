"""
Module: pigit/termui/widgets/bordered_browser.py
Description: Bordered scrollable text browser with optional title.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..component import Component, render_child
from ..primitives.frame import BoxFrame
from ..mouse import MouseEvent
from ..segment import Segment
from ..theme import get_theme
from .line_text_browser import LineTextBrowser

if TYPE_CHECKING:
    from ..surface import Surface


class BorderedBrowser(Component):
    """Box-framed scrollable browser for plain or styled line content."""

    def __init__(self, *, title: str = "", id: str | None = None) -> None:
        super().__init__(id=id)
        self._title = title
        theme = get_theme()
        self._frame = BoxFrame(0, 0, title=title or None, fg=theme.fg_dim)
        self._browser = LineTextBrowser(
            x=2,
            y=2,
            content=[],
            id=f"{id}_browser" if id else None,
        )

    def set_title(self, title: str) -> None:
        """Replace the box title."""
        self._title = title
        self._frame.title = title or None

    def set_content(self, rows: list[str] | list[list[Segment]]) -> None:
        """Replace scrollable content and reset scroll to the top."""
        if rows and isinstance(rows[0], list):
            styled: list[list[Segment]] = []
            for row in rows:
                if not isinstance(row, list):
                    raise TypeError("mixed plain/segment content is not supported")
                styled.append(row)
            self._browser.set_segment_rows(styled)
            return
        plain: list[str] = []
        for line in rows:
            if not isinstance(line, str):
                raise TypeError("mixed plain/segment content is not supported")
            plain.append(line)
        self._browser.set_plain_lines(plain)

    def scroll_up(self, step: int = 1) -> None:
        """Scroll the inner browser up."""
        self._browser.scroll_up(step)

    def scroll_down(self, step: int = 1) -> None:
        """Scroll the inner browser down."""
        self._browser.scroll_down(step)

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Delegate wheel events to the inner browser."""
        return self._browser.handle_mouse(event)

    def mount(self) -> None:
        super().mount()
        self._browser.mount()

    def unmount(self) -> None:
        self._browser.unmount()
        super().unmount()

    def resize(self, size: tuple[int, int]) -> None:
        """Size the border frame and inner browser."""
        self._size = size
        inner_w = max(1, size[0] - 2)
        inner_h = max(1, size[1] - 2)
        self._frame.set_inner_size(inner_w, inner_h)
        self._browser.x = 2
        self._browser.y = 2
        self._browser.resize((inner_w, inner_h))

    def paint(self, surface: Surface) -> None:
        w = surface.width
        h = surface.height
        if w < 2 or h < 2:
            return
        inner_h = max(1, h - 2)
        inner_w = max(1, w - 2)
        self._frame.set_inner_size(inner_w, inner_h)
        self._frame.title = self._title or None
        self._frame.draw(surface, 0, 0)
        render_child(self._browser, surface, "BorderedBrowser")
