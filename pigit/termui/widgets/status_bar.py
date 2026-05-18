"""
Module: pigit/termui/widgets/status_bar.py
Description: Single-line status bar widget.
Author: Zev
Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Callable

from .. import palette
from .._component import Component, bind_signals
from .._surface import Surface, _Subsurface
from ..reactive import Computed, Signal, ValueRef
from ..tty_io import truncate_line
from ..wcwidth_table import pad_by_width


class StatusBar(Component):
    """Single-line status bar.

    When placed inside a layout container (e.g. ``Column``), ``x`` and ``y``
    are managed by the container and manual values are ignored.
    """

    def __init__(
        self,
        text: ValueRef[str] = "",
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(x, y, size)
        self._text_src: ValueRef[str] = text
        self._unsub: Callable[[], None] | None = None
        if isinstance(text, (Signal, Computed)):
            self._text = text.value
            self._unsub = bind_signals(self, text)
        else:
            self._text = text

    def refresh(self) -> None:
        if isinstance(self._text_src, (Signal, Computed)):
            self._text = self._text_src.value

    def set_text(self, text: str) -> None:
        """Update the displayed status text."""
        self._text = text

    def destroy(self) -> None:
        """Unsubscribe from the signal and clean up resources."""
        if self._unsub:
            self._unsub()
        super().destroy()

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        text = truncate_line(self._text, surface.width)
        text = pad_by_width(text, surface.width)
        surface.draw_text_rgb(0, 0, text, fg=palette.DEFAULT_FG, bg=palette.DEFAULT_BG)
