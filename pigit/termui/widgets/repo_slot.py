"""
Module: pigit/termui/widgets/repo_slot.py
Description: Interactive Header left-slot control for opening the repo switcher.
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

_PREFIX = "@ "

# Re-export for tests that import ``repo_slot._SUFFIX``.
__all__ = ("RepoSlot", "_PREFIX", "_SUFFIX")


class RepoSlot(HeaderSlot):
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
        super().__init__(sources=[name], fg=fg, id=id)
        self._on_open = on_open

    @property
    def name(self) -> str:
        """Current repository display name."""
        return self._display_name()

    def _assemble(self, display_name: str) -> str:
        return f"{_PREFIX}{display_name}{_SUFFIX}"

    def _fixed_width(self) -> int:
        return wcswidth(_PREFIX) + wcswidth(_SUFFIX)

    def _default_fg(self) -> tuple[int, int, int]:
        return get_theme().fg_accent

    def _handle_click(self, event: MouseEvent) -> None:
        if self._on_open is not None:
            self._on_open()
