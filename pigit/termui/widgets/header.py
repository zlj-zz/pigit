"""
Module: pigit/termui/widgets/header.py
Description: Generic header bar with left/center/right segments and slot children.
Author: Zev
Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ..component import Component, bind_signals, render_child
from ..segment import Segment
from ..surface import Surface
from ..reactive import Computed, Signal, ValueRef
from ..wcwidth_table import truncate_by_width, wcswidth


class Header(Component):
    """Generic header bar with left/center/right segments and optional slot children.

    Each text slot accepts a static list, a Signal, or a Computed value.
    When a Signal/Computed changes, Header auto-refreshes.
    Center is horizontally centred; right is right-aligned.
    If total width exceeds available space, centre is dropped first,
    then left text is truncated with an ellipsis.

    Optional ``left_child`` / ``right_child`` are interactive Components placed
    in the left/right slots. They are painted and hit-tested via the normal
    child geometry contract (``x``/``y``/``_size``); Header does not hard-code
    child types. Text segments for a slot still draw in the remaining space
    beside that slot's child (after left_child, before right_child).
    """

    def __init__(
        self,
        *,
        left: ValueRef[list[Segment]] | None = None,
        center: ValueRef[list[Segment]] | None = None,
        right: ValueRef[list[Segment]] | None = None,
        left_child: Component | None = None,
        right_child: Component | None = None,
        separator: bool = True,
        sep_fg: tuple[int, int, int] = (100, 100, 100),
        id: str | None = None,
    ) -> None:
        # Slot children are chrome (paint + hit-test), not focus-tree children —
        # same pattern as OptionList header/footer slots, so resolve_focus_leaf
        # still drills into the body TabView instead of RepoSlot.
        super().__init__(id=id)

        self._separator = separator
        self._sep_fg = sep_fg
        self._left_child = left_child
        self._right_child = right_child
        if left_child is not None:
            left_child.parent = self
        if right_child is not None:
            right_child.parent = self

        self._left_src = left or []
        self._center_src = center or []
        self._right_src = right or []

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

    @property
    def left_child(self) -> Component | None:
        """Interactive component occupying the left slot, if any."""
        return self._left_child

    @property
    def right_child(self) -> Component | None:
        """Interactive component occupying the right slot, if any."""
        return self._right_child

    def mount(self) -> None:
        super().mount()
        for child in (self._left_child, self._right_child):
            if child is not None:
                child.mount()

    def unmount(self) -> None:
        for child in (self._left_child, self._right_child):
            if child is not None:
                child.unmount()
        super().unmount()

    def _hit_test(self, col: int, row: int):
        """Hit-test slot children by laid-out geometry, then this Header."""
        for child in (self._right_child, self._left_child):
            if child is None:
                continue
            width, height = child._size
            if width <= 0 or height <= 0:
                continue
            if not (child.y <= col < child.y + width and child.x <= row < child.x + height):
                continue
            hit = child._hit_test(col - (child.y - 1), row - (child.x - 1))
            if hit is not None:
                return hit
        return self, col, row

    def destroy(self) -> None:
        for unsub in self._unsubs:
            unsub()
        if self._left_child is not None:
            self._left_child.destroy()
        if self._right_child is not None:
            self._right_child.destroy()
        super().destroy()

    def resize(self, size: tuple[int, int]) -> None:
        """Propagate size and lay out slot children for paint / hit-test."""
        super().resize(size)
        self._layout_slot_children(size[0])

    def paint(self, surface: Surface) -> None:
        w = surface.width
        h = surface.height
        if w <= 0:
            return

        self._layout_slot_children(w)
        if h >= 2 and self._separator:
            self._draw_content(surface, 0, w)
            surface.fill_rect_rgb(1, 0, w, 1)
            surface.draw_text_rgb(1, 0, "─" * w, fg=self._sep_fg)
        else:
            self._draw_content(surface, 0, w)

    def _child_width(self, child: Component | None, max_width: int) -> int:
        """Preferred width of a slot child, capped at ``max_width``."""
        if child is None or max_width <= 0:
            return 0
        preferred = getattr(child, "preferred_width", None)
        if callable(preferred):
            result = preferred(max_width)
            width = result if isinstance(result, int) else 0
            return max(0, min(width, max_width))
        width, _height = child._size
        return max(0, min(width, max_width))

    def _layout_slot_children(self, width: int) -> None:
        """Set 1-based geometry on slot children so paint and hit-test agree."""
        right_w = 0
        if self._right_child is not None:
            right_w = self._child_width(self._right_child, width)
            self._right_child.x = 1
            self._right_child.y = max(1, width - right_w + 1)
            self._right_child.resize((right_w, 1))

        if self._left_child is not None:
            avail = max(0, width - right_w)
            left_w = self._child_width(self._left_child, avail)
            self._left_child.x = 1
            self._left_child.y = 1
            self._left_child.resize((left_w, 1))

    def _draw_content(self, surface: Surface, row: int, width: int) -> None:
        surface.fill_rect_rgb(row, 0, width, 1)

        left = self._get(self._left_src)
        center = self._get(self._center_src)
        right = self._get(self._right_src)

        left_child_w = self._left_child._size[0] if self._left_child is not None else 0
        right_child_w = (
            self._right_child._size[0] if self._right_child is not None else 0
        )
        right_text_w = self._slot_width(right)
        # Right text (merge/mode badges) shares the strip left of right_child.
        reserved_right = right_child_w + right_text_w

        left_text_w = self._slot_width(left)
        center_w = self._slot_width(center)

        total = (
            left_child_w
            + left_text_w
            + (2 if center_w else 0)
            + center_w
            + reserved_right
        )
        if total > width and center_w:
            center_w = 0
            total = left_child_w + left_text_w + reserved_right

        if total > width:
            max_left_text = max(0, width - reserved_right - left_child_w - 1)
            left = self._truncate_slot(left, max_left_text)

        if self._left_child is not None:
            render_child(self._left_child, surface, "Header.left_child")

        x = left_child_w
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

        if center and center_w:
            centre_x = max(0, (width - center_w) // 2)
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

        if self._right_child is not None:
            if right:
                badge_w = self._slot_width(right)
                badge_x = max(0, width - right_child_w - badge_w)
                x = badge_x
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
            render_child(self._right_child, surface, "Header.right_child")
        elif right and reserved_right:
            right_x = max(0, width - reserved_right)
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
