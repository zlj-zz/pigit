"""
Module: pigit/termui/widgets/header.py
Description: Generic header bar with left/center/right segments.
Author: Zev
Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .._component import Component, bind_signals
from .._segment import Segment
from .._surface import Surface, _Subsurface
from ..reactive import Computed, Signal, ValueRef
from ..wcwidth_table import truncate_by_width, wcswidth


class Header(Component):
    """Generic header bar with left/center/right segments.

    Each slot accepts a static list, a Signal, or a Computed value.
    When a Signal/Computed changes, Header auto-refreshes.
    Center is horizontally centred; right is right-aligned.
    If total width exceeds available space, centre is dropped first,
    then left is truncated with an ellipsis.
    """

    def __init__(
        self,
        *,
        left: ValueRef[list[Segment]] | None = None,
        center: ValueRef[list[Segment]] | None = None,
        right: ValueRef[list[Segment]] | None = None,
        separator: bool = True,
        sep_fg: tuple[int, int, int] = (100, 100, 100),
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)

        self._separator = separator
        self._sep_fg = sep_fg

        self._left_src = left or []
        self._center_src = center or []
        self._right_src = right or []

        # Auto-subscribe to Signal/Computed
        self._unsubs: list[Callable[[], None]] = []
        for src in (self._left_src, self._center_src, self._right_src):
            if isinstance(src, (Signal, Computed)):
                self._unsubs.append(bind_signals(self, src))

    def _get(self, src: ValueRef[list[Segment]]) -> list[Segment]:
        if isinstance(src, (Signal, Computed)):
            return src.value
        return src

    @property
    def left(self) -> list[Segment]:
        return self._get(self._left_src)

    def _set_src(self, attr: str, segments: list[Segment]) -> None:
        src = getattr(self, attr)
        match src:
            case Signal():
                src.set(segments)
            case Computed():
                raise TypeError("Cannot assign to a Computed slot")
            case _:
                setattr(self, attr, segments)
                self.refresh()

    @left.setter
    def left(self, segments: list[Segment]) -> None:
        self._set_src("_left_src", segments)

    @property
    def center(self) -> list[Segment]:
        return self._get(self._center_src)

    @center.setter
    def center(self, segments: list[Segment]) -> None:
        self._set_src("_center_src", segments)

    @property
    def right(self) -> list[Segment]:
        return self._get(self._right_src)

    @right.setter
    def right(self, segments: list[Segment]) -> None:
        self._set_src("_right_src", segments)

    def destroy(self) -> None:
        for unsub in self._unsubs:
            unsub()
        super().destroy()

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        w = surface.width
        h = surface.height
        if w <= 0:
            return

        if h >= 2 and self._separator:
            self._draw_content(surface, 0, w)
            surface.fill_rect_rgb(1, 0, w, 1)
            surface.draw_text_rgb(1, 0, "─" * w, fg=self._sep_fg)
        else:
            self._draw_content(surface, 0, w)

    def _draw_content(self, surface: Surface | _Subsurface, row: int, w: int) -> None:
        surface.fill_rect_rgb(row, 0, w, 1)

        left = self._get(self._left_src)
        center = self._get(self._center_src)
        right = self._get(self._right_src)

        left_w = self._slot_width(left)
        center_w = self._slot_width(center)
        right_w = self._slot_width(right)

        # Drop centre if total exceeds width
        total = left_w + (2 if center_w else 0) + center_w + right_w
        if total > w and center_w:
            center_w = 0
            total = left_w + right_w

        # Truncate left if still exceeds
        if total > w:
            max_left = max(0, w - right_w - 1)
            left = self._truncate_slot(left, max_left)
            left_w = self._slot_width(left)

        # Draw left
        x = 0
        for seg in left:
            surface.draw_text_rgb(
                row,
                x,
                seg.text,
                fg=seg.fg,
                bg=seg.bg,
                style_flags=seg.style_flags,
            )
            x += wcswidth(seg.text)

        # Draw centre
        if center and center_w:
            centre_x = max(0, (w - center_w) // 2)
            x = centre_x
            for seg in center:
                surface.draw_text_rgb(
                    row,
                    x,
                    seg.text,
                    fg=seg.fg,
                    bg=seg.bg,
                    style_flags=seg.style_flags,
                )
                x += wcswidth(seg.text)

        # Draw right
        if right and right_w:
            right_x = max(0, w - right_w)
            x = right_x
            for seg in right:
                surface.draw_text_rgb(
                    row,
                    x,
                    seg.text,
                    fg=seg.fg,
                    bg=seg.bg,
                    style_flags=seg.style_flags,
                )
                x += wcswidth(seg.text)

    @staticmethod
    def _slot_width(slot: Sequence[Segment]) -> int:
        return sum(wcswidth(seg.text) for seg in slot)

    @staticmethod
    def _truncate_slot(slot: Sequence[Segment], max_width: int) -> list[Segment]:
        if max_width <= 0 or not slot:
            return []
        result: list[Segment] = []
        current_w = 0
        for seg in slot:
            text_w = wcswidth(seg.text)
            if current_w + text_w > max_width - 1:
                avail = max_width - current_w - 1
                if avail > 0:
                    truncated = truncate_by_width(seg.text, avail) + "…"
                    result.append(
                        Segment(
                            truncated, fg=seg.fg, bg=seg.bg, style_flags=seg.style_flags
                        )
                    )
                break
            result.append(seg)
            current_w += text_w
        return result
