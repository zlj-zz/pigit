"""
Module: pigit/termui/widgets/sheet.py
Description: Bottom sheet panel (SHEET layer).
Author: Zev
Date: 2026-05-18
"""

from __future__ import annotations

from .. import palette
from .._component import Component
from .._surface import Surface, _Subsurface
from ..types import OverlayDispatchResult

_BOX_CORNER_TL = "╭"
_BOX_CORNER_TR = "╮"


class Sheet(Component):
    """Bottom sheet panel, similar to mobile bottom sheet (SHEET layer)."""

    def __init__(
        self,
        child: Component,
        height: int = 8,
        size: tuple[int, int] | None = None,
        show_border: bool = False,
    ) -> None:
        super().__init__(size=size)
        self._child = child
        child.parent = self
        self._target_height = height
        self._show_border = show_border
        self._child_dispatch = getattr(child, "dispatch_overlay_key", None)
        self.open = True

    @property
    def presented_child(self) -> Component | None:
        """Delegate focus and inspector queries to the wrapped child."""
        return self._child

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        """Forward overlay keys to the child component if supported."""
        if self._child_dispatch is not None:
            return self._child_dispatch(key)
        self._child._handle_event(key)
        return OverlayDispatchResult.HANDLED_EXPLICIT

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        if self._size[1] <= 0:
            return
        y = surface.height - self._size[1]
        sub = surface.subsurface(y, 0, self._size[0], self._size[1])
        # Clear sheet background so underlying content does not bleed through.
        sub.fill_rect_rgb(0, 0, sub.width, sub.height, palette.DEFAULT_BG)
        border_h = 1 if self._show_border else 0
        if self._show_border:
            if sub.width >= 2:
                fg, bg = palette.DEFAULT_FG_DIM, palette.DEFAULT_BG
                sub.draw_text_rgb(0, 0, _BOX_CORNER_TL, fg=fg, bg=bg)
                sub.draw_text_rgb(0, sub.width - 1, _BOX_CORNER_TR, fg=fg, bg=bg)
                if sub.width > 2:
                    sub.draw_hline_rgb(0, 1, sub.width - 2, fg=fg, bg=bg)
            else:
                sub.draw_hline_rgb(
                    0, 0, sub.width, fg=palette.DEFAULT_FG_DIM, bg=palette.DEFAULT_BG
                )
        if self._size[1] > border_h:
            child_sub = sub.subsurface(border_h, 0, sub.width, sub.height - border_h)
            self._child._render_surface(child_sub)

    def hide(self) -> None:
        """Close the sheet."""
        self.open = False

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the sheet and its child to the given terminal size."""
        sheet_h = min(self._target_height, size[1] // 2)
        new_size = (size[0], sheet_h)
        if getattr(self, "_size", None) == new_size:
            return
        self._size = new_size
        border_h = 1 if self._show_border else 0
        child_h = max(1, sheet_h - border_h)
        self._child.resize((size[0], child_h))
