"""
Module: pigit/termui/widgets/header_slot.py
Description: Shared Header left/right slot base (signal bind, truncate, click).
Author: Zev
Date: 2026-08-29
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ..component import Component, bind_signals
from .._runtime_context import request_render
from ..mouse import MouseButton, MouseEvent, MouseKind
from ..reactive import Computed, Signal, ValueRef
from ..segment import Segment
from ..surface import Surface
from ..wcwidth_table import truncate_by_width, wcswidth
from .. import palette

_SUFFIX = " ▾"


class HeaderSlot(Component):
    """Interactive Header slot: signal-driven label, narrow truncate, click open.

    Subclasses supply label assembly and click forwarding via thin hooks.
    ``sources[0]`` is the display name used for truncation.
    """

    def __init__(
        self,
        *,
        sources: Sequence[ValueRef[str] | str],
        fg: tuple[int, int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._sources: list[ValueRef[str] | str] = list(sources)
        self._fg = fg
        self._unsubs: list[Callable[[], None]] = []
        for src in self._sources:
            if isinstance(src, (Signal, Computed)):
                self._unsubs.append(bind_signals(self, src))

    def _values(self) -> list[str]:
        """Current string values for every bound source."""
        out: list[str] = []
        for src in self._sources:
            if isinstance(src, (Signal, Computed)):
                out.append(src.value)
            else:
                out.append(src)
        return out

    def _display_name(self) -> str:
        """Display name for truncation (``sources[0]``)."""
        values = self._values()
        return values[0] if values else ""

    def _label_text(self) -> str:
        """Full label from the complete display name."""
        return self._assemble(self._display_name())

    def _assemble(self, display_name: str) -> str:
        """Build the painted label around ``display_name`` (subclass implements)."""
        raise NotImplementedError

    def _fixed_width(self) -> int:
        """Display width of non-name chrome reserved during truncation."""
        raise NotImplementedError

    def _default_fg(self) -> tuple[int, int, int]:
        """Theme foreground when the constructor did not set ``fg``."""
        raise NotImplementedError

    def _handle_click(self, event: MouseEvent) -> None:
        """Forward a left press to the slot's open callback."""
        raise NotImplementedError

    def _label_fg(self) -> tuple[int, int, int]:
        return self._fg if self._fg is not None else self._default_fg()

    def refresh(self) -> None:
        """Repaint when a bound signal changes (base refresh is a no-op)."""
        request_render()

    def destroy(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        super().destroy()

    def preferred_width(self, max_width: int = 999) -> int:
        """Width of the full label, capped at ``max_width``."""
        return min(wcswidth(self._label_text()), max(0, max_width))

    def as_segments(self) -> list[Segment]:
        """Return the label as segments (tests / debugging)."""
        return [
            Segment(
                self._label_text(),
                fg=self._label_fg(),
                style_flags=palette.STYLE_BOLD,
            )
        ]

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Left press opens the slot action via ``_handle_click``."""
        if event.kind is not MouseKind.PRESS:
            return False
        if event.button is not MouseButton.LEFT:
            return False
        self._handle_click(event)
        return True

    def paint(self, surface: Surface) -> None:
        """Draw the label, truncating the display name when the slot is narrow."""
        width = surface.width
        if width <= 0:
            return
        surface.fill_rect_rgb(0, 0, width, 1)
        text = self._assemble(self._display_name())
        if wcswidth(text) > width:
            fixed = self._fixed_width()
            avail = max(0, width - fixed)
            name = truncate_by_width(self._display_name(), avail) if avail else ""
            if avail and wcswidth(name) >= avail and avail > 1:
                name = truncate_by_width(self._display_name(), avail - 1) + "…"
            text = self._assemble(name)
            if wcswidth(text) > width:
                text = truncate_by_width(text, width - 1) + "…" if width > 1 else ""
        surface.draw_text_rgb(
            0,
            0,
            text,
            fg=self._label_fg(),
            style_flags=palette.STYLE_BOLD,
        )
