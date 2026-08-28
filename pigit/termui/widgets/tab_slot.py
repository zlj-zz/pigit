"""
Module: pigit/termui/widgets/tab_slot.py
Description: Interactive Header right-slot control for opening the panel picker.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Callable

from ..component import Component, bind_signals
from .._runtime_context import request_render
from ..mouse import MouseButton, MouseEvent, MouseKind
from ..reactive import Computed, Signal, ValueRef
from ..segment import Segment
from ..surface import Surface
from ..theme import get_theme
from ..wcwidth_table import truncate_by_width, wcswidth
from .. import palette

_SUFFIX = " ▾"


class TabSlot(Component):
    """Header right-slot child that paints ``{name} [{key}] ▾`` and opens the picker.

    Click (left press) invokes ``on_open`` with the local mouse event so the
    app can derive an anchored Popup offset from slot geometry + click column.
    """

    def __init__(
        self,
        *,
        tab_name: ValueRef[str] | str = "",
        tab_key: ValueRef[str] | str = "",
        on_open: Callable[[MouseEvent], None] | None = None,
        fg: tuple[int, int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._name_src = tab_name
        self._key_src = tab_key
        self._on_open = on_open
        self._fg = fg
        self._unsubs: list[Callable[[], None]] = []
        for src in (tab_name, tab_key):
            if isinstance(src, (Signal, Computed)):
                self._unsubs.append(bind_signals(self, src))

    @property
    def label_name(self) -> str:
        """Current panel display name from the bound source."""
        src = self._name_src
        if isinstance(src, (Signal, Computed)):
            return src.value
        return src

    @property
    def label_key(self) -> str:
        """Current panel digit key (e.g. ``1``), or empty."""
        src = self._key_src
        if isinstance(src, (Signal, Computed)):
            return src.value
        return src

    def refresh(self) -> None:
        """Repaint when tab name/key signals change (base refresh is a no-op)."""
        request_render()

    def _label_fg(self) -> tuple[int, int, int]:
        return self._fg if self._fg is not None else get_theme().fg_muted

    def preferred_width(self, max_width: int = 999) -> int:
        """Width of the full label, capped at ``max_width``."""
        return min(wcswidth(self._label_text()), max(0, max_width))

    def _label_text(self) -> str:
        name = self.label_name
        key = self.label_key
        if key:
            return f"{name} [{key}]{_SUFFIX}"
        return f"{name}{_SUFFIX}"

    def destroy(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        super().destroy()

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Left press opens the panel picker, forwarding the local event."""
        if event.kind is not MouseKind.PRESS:
            return False
        if event.button is not MouseButton.LEFT:
            return False
        if self._on_open is not None:
            self._on_open(event)
        return True

    def paint(self, surface: Surface) -> None:
        """Draw the tab label, truncating the name when the slot is narrow."""
        width = surface.width
        if width <= 0:
            return
        surface.fill_rect_rgb(0, 0, width, 1)
        text = self._label_text()
        if wcswidth(text) > width:
            key = self.label_key
            key_part = f" [{key}]" if key else ""
            fixed = wcswidth(key_part) + wcswidth(_SUFFIX)
            avail = max(0, width - fixed)
            name = truncate_by_width(self.label_name, avail) if avail else ""
            if avail and wcswidth(name) >= avail and avail > 1:
                name = truncate_by_width(self.label_name, avail - 1) + "…"
            text = f"{name}{key_part}{_SUFFIX}"
            if wcswidth(text) > width:
                text = truncate_by_width(text, width - 1) + "…" if width > 1 else ""
        surface.draw_text_rgb(
            0,
            0,
            text,
            fg=self._label_fg(),
            style_flags=palette.STYLE_BOLD,
        )

    def as_segments(self) -> list[Segment]:
        """Return the label as segments (tests / debugging)."""
        return [
            Segment(
                self._label_text(),
                fg=self._label_fg(),
                style_flags=palette.STYLE_BOLD,
            )
        ]
