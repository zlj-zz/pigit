"""
Module: pigit/termui/widgets/sheet.py
Description: Edge sheet panel (top or bottom) on the SHEET layer.
Author: Zev
Date: 2026-05-18
"""

from __future__ import annotations

from typing import Literal

from ..component import Component
from ..surface import Surface
from ..theme import get_theme
from ..types import OverlayDispatchResult
from ..wcwidth_table import truncate_by_width, wcswidth

DEFAULT_SHEET_HEIGHT = 8
DEFAULT_MAX_FRACTION = 1 / 3
DEFAULT_HARD_CAP_FRACTION = 1 / 2
MIN_SHEET_HEIGHT = 3

TitleAlign = Literal["left", "center", "right"]

_RULE_CHAR = "─"
_ELLIPSIS = "…"


def compose_edge_rule(
    width: int,
    core: str | None = None,
    *,
    align: TitleAlign = "right",
) -> tuple[str, str, str]:
    """Build one facing-edge rule as ``(left_fill, core, right_fill)``.

    ``core`` is a caller-composed center slot (e.g. `` · title · ``) painted
    verbatim; fills are ``─``. At least one fill cell is kept on each side
    when width allows. Oversized cores are truncated with an ellipsis. When
    the core cannot fit, returns a plain rule (empty core).
    """
    if width <= 0:
        return "", "", ""
    plain = (_RULE_CHAR * width, "", "")
    if not core:
        return plain

    # Reserve one rule cell on each side when possible.
    max_core = width - 2 if width >= 2 else 0
    core_w = wcswidth(core)
    if core_w > max_core:
        if max_core <= 1:
            return plain
        core = truncate_by_width(core, max_core - 1) + _ELLIPSIS
        core_w = wcswidth(core)

    fill = width - core_w
    if align == "left":
        left_n, right_n = 1, fill - 1
    elif align == "center":
        left_n = fill // 2
        right_n = fill - left_n
        if left_n == 0 and fill >= 2:
            left_n, right_n = 1, fill - 1
        elif right_n == 0 and fill >= 2:
            right_n, left_n = 1, fill - 1
    else:
        left_n, right_n = fill - 1, 1
    return _RULE_CHAR * left_n, core, _RULE_CHAR * right_n


class Sheet(Component):
    """Edge sheet panel (top or bottom) on the SHEET layer.

    Default chrome: no fill color (``bg=None`` — cells keep the terminal
    default background, not a theme slab) and a facing-edge rule
    (``show_edge_rule=True``): a full-width ``─`` line with an optional
    center slot. ``title_core`` is a caller-composed slot painted verbatim
    (e.g. `` · Switch repo · ``). The rule paints with ``edge_fg`` when
    given (a brand accent, for instance), otherwise the theme's dim/muted
    foregrounds. Callers that need a solid slab or a rule-less one-line
    input pass those explicitly.

    ``top_pad`` / ``bottom_pad`` reserve app chrome rows (header / footer) so
    the sheet paints in the body region and does not cover those hints.
    """

    @staticmethod
    def height_cap_fraction(max_fraction: float = DEFAULT_MAX_FRACTION) -> float:
        """Return the terminal-height fraction used as the sheet resize ceiling."""
        return max(DEFAULT_HARD_CAP_FRACTION, max_fraction)

    @staticmethod
    def clamp_height(
        rows: list,
        term_h: int,
        *,
        border: int = 1,
        max_fraction: float = DEFAULT_HARD_CAP_FRACTION,
    ) -> int:
        """Clamp sheet height including edge-rule row.

        Args:
            rows: Content rows displayed inside the sheet.
            term_h: Terminal height in rows.
            border: Extra rows reserved for chrome above/below content.
            max_fraction: Maximum fraction of ``term_h`` (never below half).

        Returns:
            Clamped sheet height in terminal rows.
        """
        cap = max(
            MIN_SHEET_HEIGHT, int(term_h * Sheet.height_cap_fraction(max_fraction))
        )
        return min(max(len(rows) + border, MIN_SHEET_HEIGHT), cap)

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
        ``[MIN_SHEET_HEIGHT, min(term_h * max_fraction, term_h * max(max_fraction, 1/2))]``.

        When ``height`` is given, clamps to
        ``[MIN_SHEET_HEIGHT, term_h * max(max_fraction, 1/2)]``;
        ``max_fraction`` only affects that ceiling, not the preferred value.
        """
        cap_fraction = Sheet.height_cap_fraction(max_fraction)
        hard_cap = max(MIN_SHEET_HEIGHT, int(term_h * cap_fraction))
        if height is None:
            pref = getattr(child, "preferred_sheet_height", None)
            if callable(pref):
                want = pref(term_h)
                height = want if isinstance(want, int) else DEFAULT_SHEET_HEIGHT
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
        title_core: str | None = None,
        title_align: TitleAlign = "right",
        edge: Literal["top", "bottom"] = "bottom",
        bg: tuple[int, int, int] | None = None,
        top_pad: int = 0,
        bottom_pad: int = 0,
        height_cap_fraction: float = DEFAULT_HARD_CAP_FRACTION,
        edge_fg: tuple[int, int, int] | None = None,
    ) -> None:
        super().__init__(size=size)
        self._child = child
        child.parent = self
        self._target_height = height
        self._height_cap_fraction = height_cap_fraction
        self._show_edge_rule = show_edge_rule
        self._title_core = title_core
        self._title_align: TitleAlign = title_align
        self._edge = edge
        self._bg = bg
        self._edge_fg = edge_fg
        self._top_pad = top_pad
        self._bottom_pad = bottom_pad
        self._child_dispatch = getattr(child, "dispatch_overlay_key", None)
        self.open = True

    def _origin_row(self, term_h: int, sheet_h: int) -> int:
        """0-based row of the sheet's top edge on a terminal of *term_h*."""
        if self._edge == "top":
            return self._top_pad
        return max(0, term_h - sheet_h - self._bottom_pad)

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

    def paint(self, surface: Surface) -> None:
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
        self._child.paint(child_sub)

    def _sheet_bg(self) -> tuple[int, int, int] | None:
        """Return the sheet fill color.

        ``None`` means no RGB background (terminal default), not see-through
        to the body layer. The sheet still clears its region to spaces.
        """
        return self._bg

    def _draw_rule(self, sub: Surface, row: int) -> None:
        """Draw the facing-edge rule as a full-width line, optional title core."""
        theme = get_theme()
        accent = self._edge_fg
        fg_rule, fg_title = (
            (accent, accent) if accent is not None else (theme.fg_dim, theme.fg_muted)
        )
        bg = self._sheet_bg()
        left, core, right = compose_edge_rule(
            sub.width,
            self._title_core,
            align=self._title_align,
        )
        col = 0
        if left:
            sub.draw_text_rgb(row, col, left, fg=fg_rule, bg=bg)
            col += wcswidth(left)
        if core:
            sub.draw_text_rgb(row, col, core, fg=fg_title, bg=bg)
            col += wcswidth(core)
        if right:
            sub.draw_text_rgb(row, col, right, fg=fg_rule, bg=bg)

    def hide(self) -> None:
        """Close the sheet."""
        self.open = False

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the sheet and its child to the given terminal size.

        The height cap deducts both chrome pads so the sheet always fits in
        the body region between header and footer, regardless of edge.
        """
        body_rows = size[1] - self._top_pad - self._bottom_pad
        cap_rows = max(
            MIN_SHEET_HEIGHT,
            int(body_rows * self._height_cap_fraction),
        )
        sheet_h = min(self._target_height, cap_rows)
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
