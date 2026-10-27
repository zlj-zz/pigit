"""
Module: pigit/termui/widgets/tab_slot.py
Description: Interactive Header right-slot control for opening the panel picker.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Callable

from ..mouse import MouseEvent
from ..reactive import ValueRef
from ..theme import get_theme
from ..wcwidth_table import wcswidth

from .header_slot import HeaderSlot, _SUFFIX


class TabSlot(HeaderSlot):
    """Header right-slot child that paints ``{name} [{key}/{total}] ▾`` and opens the picker.

    Click (left press) invokes ``on_open`` with the local mouse event so the
    app can derive an anchored Popup offset from slot geometry + click column.
    """

    def __init__(
        self,
        *,
        tab_name: ValueRef[str] | str = "",
        tab_key: ValueRef[str] | str = "",
        tab_total: ValueRef[str] | str = "",
        on_open: Callable[[MouseEvent], None] | None = None,
        fg: tuple[int, int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(sources=[tab_name, tab_key, tab_total], fg=fg, id=id)
        self._on_open = on_open

    @property
    def label_name(self) -> str:
        """Current panel display name from the bound source."""
        return self._display_name()

    @property
    def label_key(self) -> str:
        """Current panel digit key (e.g. ``1``), or empty."""
        values = self._values()
        return values[1] if len(values) > 1 else ""

    @property
    def label_total(self) -> str:
        """Number of product pages, or empty when the slot was not given one."""
        values = self._values()
        return values[2] if len(values) > 2 else ""

    def _key_part(self) -> str:
        key = self.label_key
        total = self.label_total
        if not key:
            return ""
        return f" [{key}/{total}]" if total else f" [{key}]"

    def _assemble(self, display_name: str) -> str:
        return f"{display_name}{self._key_part()}{_SUFFIX}"

    def _fixed_width(self) -> int:
        return wcswidth(self._key_part()) + wcswidth(_SUFFIX)

    def _default_fg(self) -> tuple[int, int, int]:
        return get_theme().fg_muted

    def _handle_click(self, event: MouseEvent) -> None:
        if self._on_open is not None:
            self._on_open(event)
