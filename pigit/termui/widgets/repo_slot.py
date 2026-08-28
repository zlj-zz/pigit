"""
Module: pigit/termui/widgets/repo_slot.py
Description: Interactive Header left-slot control for opening the repo switcher.
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

_PREFIX = "@ "
_SUFFIX = " ▾"


class RepoSlot(Component):
    """Header left-slot child that paints ``@ name ▾`` and opens the switcher.

    Click (left press) invokes ``on_open``. The app also binds ``@`` to the same
    callback; when search/overlays swallow keys, the mouse path remains reachable.
    """

    def __init__(
        self,
        *,
        name: ValueRef[str] | str = "",
        on_open: Callable[[], None] | None = None,
        fg: tuple[int, int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._name_src = name
        self._on_open = on_open
        self._fg = fg
        self._unsubs: list[Callable[[], None]] = []
        if isinstance(name, (Signal, Computed)):
            self._unsubs.append(bind_signals(self, name))

    @property
    def name(self) -> str:
        """Current repository display name."""
        src = self._name_src
        if isinstance(src, (Signal, Computed)):
            return src.value
        return src

    def refresh(self) -> None:
        """Repaint when the repo-name signal changes (base refresh is a no-op)."""
        request_render()

    def _label_fg(self) -> tuple[int, int, int]:
        return self._fg if self._fg is not None else get_theme().fg_accent

    def preferred_width(self, max_width: int = 999) -> int:
        """Width of the full ``@ name ▾`` label, capped at ``max_width``."""
        return min(wcswidth(self._label_text()), max(0, max_width))

    def _label_text(self) -> str:
        return f"{_PREFIX}{self.name}{_SUFFIX}"

    def destroy(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        super().destroy()

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Left press opens the repo switcher."""
        if event.kind is not MouseKind.PRESS:
            return False
        if event.button is not MouseButton.LEFT:
            return False
        if self._on_open is not None:
            self._on_open()
        return True

    def paint(self, surface: Surface) -> None:
        """Draw the ``@ name ▾`` label, truncating the name when the slot is narrow."""
        width = surface.width
        if width <= 0:
            return
        surface.fill_rect_rgb(0, 0, width, 1)
        text = self._label_text()
        if wcswidth(text) > width:
            fixed = wcswidth(_PREFIX) + wcswidth(_SUFFIX)
            avail = max(0, width - fixed)
            name = truncate_by_width(self.name, avail) if avail else ""
            if avail and wcswidth(name) >= avail and avail > 1:
                name = truncate_by_width(self.name, avail - 1) + "…"
            text = f"{_PREFIX}{name}{_SUFFIX}"
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
