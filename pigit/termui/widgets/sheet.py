"""
Module: pigit/termui/widgets/sheet.py
Description: Edge sheet panel (top or bottom) on the SHEET layer.
Author: Zev
Date: 2026-05-18
"""

from __future__ import annotations

from typing import Literal

from ..component import Component
from ..surface import Surface, _Subsurface
from ..theme import get_theme
from ..types import OverlayDispatchResult

_BOX_CORNER_TL = "╭"
_BOX_CORNER_TR = "╮"
_BOX_CORNER_BL = "╰"
_BOX_CORNER_BR = "╯"

DEFAULT_SHEET_HEIGHT = 8
DEFAULT_MAX_FRACTION = 1 / 3
MIN_SHEET_HEIGHT = 3


class Sheet(Component):
    """Edge sheet panel (top or bottom) on the SHEET layer.

    Default chrome: no fill color (``bg=None`` — cells keep the terminal
    default background, not a theme slab) and a facing-edge rule
    (``show_edge_rule=True``). Callers that need a solid slab or a rule-less
    one-line input pass those explicitly.
    """

    @staticmethod
    def clamp_height(rows: list, term_h: int, *, border: int = 1) -> int:
        """Clamp sheet height to ``[3, term_h // 2]`` including edge-rule row.

        Args:
            rows: Content rows displayed inside the sheet.
            term_h: Terminal height in rows.
            border: Extra rows reserved for chrome above/below content.

        Returns:
            Clamped sheet height in terminal rows.
        """
        return min(max(len(rows) + border, 3), max(3, term_h // 2))

    @staticmethod
    def resolve_height(
        child: Component,
        term_h: int,
        *,
        height: int | None = None,
        max_fraction: float = DEFAULT_MAX_FRACTION,
    ) -> int:
        """Resolve sheet height from an explicit value or the child's preference.

        When ``height`` is omitted, calls ``child.preferred_sheet_height(term_h)``
        if present (else :data:`DEFAULT_SHEET_HEIGHT`), then clamps to
        ``[MIN_SHEET_HEIGHT, min(term_h // 2, term_h * max_fraction)]``.

        When ``height`` is given, only clamps to ``[MIN_SHEET_HEIGHT, term_h // 2]``;
        ``max_fraction`` does not apply.
        """
        hard_cap = max(MIN_SHEET_HEIGHT, term_h // 2)
        if height is None:
            pref = getattr(child, "preferred_sheet_height", None)
            if callable(pref):
                height = int(pref(term_h))
            else:
                height = DEFAULT_SHEET_HEIGHT
            soft_cap = max(MIN_SHEET_HEIGHT, int(term_h * max_fraction))
            ceiling = min(soft_cap, hard_cap)
        else:
            ceiling = hard_cap
        return min(max(height, MIN_SHEET_HEIGHT), ceiling)

    def __init__(
        self,
        child: Component,
        height: int = 8,
        size: tuple[int, int] | None = None,
        *,
        show_edge_rule: bool = True,
        edge: Literal["top", "bottom"] = "bottom",
        bg: tuple[int, int, int] | None = None,
    ) -> None:
        super().__init__(size=size)
        self._child = child
        child.parent = self
        self._target_height = height
        self._show_edge_rule = show_edge_rule
        self._edge = edge
        self._bg = bg
        self._child_dispatch = getattr(child, "dispatch_overlay_key", None)
        self.open = True

    def _origin_row(self, term_h: int, sheet_h: int) -> int:
        """Return 0-based row of the sheet's top edge on a terminal of *term_h*."""
        if self._edge == "top":
            return 0
        return term_h - sheet_h

    def _edge_rule_row(self, sheet_h: int) -> int | None:
        """0-based row of the facing-edge rule, or None when disabled."""
        if not self._show_edge_rule:
            return None
        if self._edge == "top":
            return sheet_h - 1
        return 0

    @property
    def focus_child(self) -> Component | None:
        """Delegate focus to the wrapped child."""
        return self._child

    @property
    def presentation_child(self) -> Component | None:
        """Delegate chrome queries to the wrapped child."""
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
        y = self._origin_row(surface.height, self._size[1])
        sub = surface.subsurface(y, 0, self._size[0], self._size[1])
        sub.fill_rect_rgb(0, 0, sub.width, sub.height, self._sheet_bg())
        rule_row = self._edge_rule_row(self._size[1])
        if rule_row is not None:
            self._draw_rule(sub, rule_row)
        child_h = self._size[1] - (1 if rule_row is not None else 0)
        if child_h <= 0:
            return
        child_y = 1 if rule_row == 0 else 0
        child_sub = sub.subsurface(child_y, 0, sub.width, child_h)
        self._child._render_surface(child_sub)

    def _sheet_bg(self) -> tuple[int, int, int] | None:
        """Return the sheet fill color.

        ``None`` means no RGB background (terminal default), not see-through
        to the body layer. The sheet still clears its region to spaces.
        """
        return self._bg

    def _draw_rule(self, sub: Surface | _Subsurface, row: int) -> None:
        """Draw the facing-edge rule: ╭─╮ on the top of a bottom sheet, ╰─╯ on the bottom of a top sheet."""
        theme = get_theme()
        fg, bg = theme.fg_dim, self._sheet_bg()
        left, right = (
            (_BOX_CORNER_BL, _BOX_CORNER_BR)
            if self._edge == "top"
            else (_BOX_CORNER_TL, _BOX_CORNER_TR)
        )
        if sub.width >= 2:
            sub.draw_text_rgb(row, 0, left, fg=fg, bg=bg)
            sub.draw_text_rgb(row, sub.width - 1, right, fg=fg, bg=bg)
            if sub.width > 2:
                sub.draw_hline_rgb(row, 1, sub.width - 2, fg=fg, bg=bg)
        else:
            sub.draw_hline_rgb(row, 0, sub.width, fg=fg, bg=bg)

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
        origin = self._origin_row(size[1], sheet_h)
        self.x = origin + 1
        self.y = 1
        rule_h = 1 if self._show_edge_rule else 0
        child_h = max(1, sheet_h - rule_h)
        self._child.resize((size[0], child_h))

    def _hit_test(self, col: int, row: int) -> tuple[Component, int, int] | None:
        """Hit-test the sheet region, delegating to the wrapped child."""
        w, h = self._size
        if w <= 0 or h <= 0:
            return None
        if not (self.y <= col < self.y + w and self.x <= row < self.x + h):
            return None
        child = self._child
        cw, ch = child._size
        if cw <= 0 or ch <= 0:
            return self, col, row
        local_col = col - (self.y - 1)
        local_row = row - (self.x - 1)
        rule_row = self._edge_rule_row(h)
        # ``local_row`` is 1-based; ``rule_row`` is 0-based within the sheet.
        if rule_row is not None and local_row == rule_row + 1:
            return self, col, row
        child_row = local_row if rule_row != 0 else local_row - 1
        hit = child._hit_test(local_col, child_row)
        return hit if hit is not None else (self, col, row)
