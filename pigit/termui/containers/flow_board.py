"""
Module: pigit/termui/containers/flow_board.py
Description: Flow layout for variable-size blocks on a pannable canvas.
Author: Zev
Date: 2026-10-06
"""

from __future__ import annotations

from collections.abc import Sequence

from ..component import Component
from ..mouse import MouseButton, MouseEvent, MouseKind
from ..palette import DEFAULT_FG_DIM
from ..surface import Surface
from .._runtime_context import request_render

# Space between two blocks on a row, and between rows.
COL_GAP = 2
ROW_GAP = 1
# Columns or rows moved per mouse-wheel tick, and per pan key press.
PAN_STEP = 5
# One per edge, drawn only when the canvas extends past the window that way.
_MARK_LEFT = "‹"
_MARK_RIGHT = "›"
_MARK_UP = "▲"
_MARK_DOWN = "▼"


class FlowBoard(Component):
    """Lay out variable-size blocks left to right, wrapping when one would not show.

    A block is placed on the current row unless less than half of it would be
    visible there, in which case it starts a new row. It may still overhang the
    right edge by up to half its width; the overhang is reachable by panning.

    Blocks are **not** framework children. ``render_child`` clamps a child's
    ``x``/``y`` to zero, so a child could not express being scrolled off the
    left or the top; the board therefore holds its blocks, paints them onto a
    canvas of its own, and blits the visible window into the surface it is
    given.
    """

    def __init__(
        self,
        blocks: Sequence[Component],
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)
        self._blocks = list(blocks)
        self._placements: list[tuple[Component, int, int]] = []
        self._content_size: tuple[int, int] = (0, 0)
        self._pan_x = 0
        self._pan_y = 0

    @property
    def content_size(self) -> tuple[int, int]:
        """Size of the canvas the blocks were laid out on."""
        return self._content_size

    @property
    def viewport_size(self) -> tuple[int, int]:
        """Width and height of the window onto that canvas."""
        return self._size

    @property
    def pan(self) -> tuple[int, int]:
        """Current top-left window offset into the canvas."""
        return (self._pan_x, self._pan_y)

    def mount(self) -> None:
        super().mount()
        for block in self._blocks:
            block.mount()

    def unmount(self) -> None:
        for block in self._blocks:
            block.unmount()
        super().unmount()

    def resize(self, size: tuple[int, int]) -> None:
        if self._size == size:
            return  # unchanged width means the same wrapping, so the same layout
        # Which block the window is looking at has to be read before the new
        # size lands, or the anchor is computed against a window that never
        # existed.
        anchor = self._visible_block()
        super().resize(size)
        self._relayout(anchor)

    def _relayout(self, anchor: Component | None = None) -> None:
        """Place every block for the current width, then keep the pan in range.

        The layout depends on the board's *width*, not on the canvas width it
        produced last time: a block can only wrap once there is somewhere to
        wrap to. So a resize can both move blocks and shrink the canvas --
        narrowing the window wraps more, which makes the canvas *smaller* and
        would drag the window back to the left if the pan were only clamped.
        *anchor* is the block to keep in view instead.

        Placements are ``(block, x, y)`` in the framework's own convention:
        ``x`` counts rows and ``y`` counts columns, as ``Component.x``/``y``
        and ``Surface.subsurface(row, col, ...)`` do. Blocks therefore advance
        along ``y`` and wrap onto a greater ``x``.
        """
        viewport_w = self._size[0]
        placements: list[tuple[Component, int, int]] = []
        x = y = 0
        row_h = 0
        col_end = 0
        for block in self._blocks:
            natural = block.natural_size
            if natural is None:
                raise ValueError(
                    f"{type(block).__name__} has no natural_size; FlowBoard cannot "
                    "place a block that does not say how big it needs to be"
                )
            w, h = natural
            if y > 0 and viewport_w - y < w / 2:
                y = 0
                x += row_h + ROW_GAP
                row_h = 0
            placements.append((block, x, y))
            block.resize((w, h))
            col_end = max(col_end, y + w)
            y += w + COL_GAP
            row_h = max(row_h, h)
        self._placements = placements
        self._content_size = (col_end, x + row_h)
        self._reveal(anchor)
        self._clamp_pan()

    def _visible_block(self) -> Component | None:
        """The block the window is nearest to looking at, if it shows any.

        Not "the block under the window's middle": a window is usually taller
        than the blocks on it, so its middle is often blank.
        """
        vw, vh = self._size
        centre_row = self._pan_x + vh / 2
        centre_col = self._pan_y + vw / 2
        nearest: Component | None = None
        nearest_distance = 0.0
        for block, x, y in self._placements:
            w, h = block._size
            if (
                y >= self._pan_y + vw
                or y + w <= self._pan_y
                or x >= self._pan_x + vh
                or x + h <= self._pan_x
            ):
                continue  # entirely off screen
            distance = abs((x + h / 2) - centre_row) + abs((y + w / 2) - centre_col)
            if nearest is None or distance < nearest_distance:
                nearest, nearest_distance = block, distance
        return nearest

    def _reveal(self, block: Component | None) -> None:
        """Scroll a block back into the window, minimally.

        Its top-left corner is brought to the window's edge: enough to keep it
        on screen after a relayout, without trying to preserve how much of it
        was showing, which no longer means anything once the canvas changed.
        """
        if block is None:
            return
        vw, vh = self._size
        for placed, x, y in self._placements:
            if placed is not block:
                continue
            w, h = placed._size
            if y < self._pan_y or y + w > self._pan_y + vw:
                self._pan_y = y
            if x < self._pan_x or x + h > self._pan_x + vh:
                self._pan_x = x
            return

    def _clamp_pan(self) -> None:
        """Keep the window inside the canvas."""
        content_w, content_h = self._content_size
        viewport_w, viewport_h = self._size
        self._pan_x = max(0, min(self._pan_x, content_h - viewport_h))
        self._pan_y = max(0, min(self._pan_y, content_w - viewport_w))

    def pan_by(self, *, rows: int = 0, cols: int = 0) -> None:
        """Move the window, stopping at the canvas edges.

        Args:
            rows: Rows to scroll down by; negative scrolls up.
            cols: Columns to scroll right by; negative scrolls left.
        """
        self._pan_x += rows
        self._pan_y += cols
        self._clamp_pan()
        request_render()

    def pan_home(self) -> None:
        """Return the window to the canvas origin."""
        self._pan_x = 0
        self._pan_y = 0
        request_render()

    def paint(self, surface: Surface) -> None:
        canvas = _new_surface(*self._content_size)
        for block, x, y in self._placements:
            w, h = block._size
            if w <= 0 or h <= 0:
                continue
            block.paint(canvas.subsurface(x, y, w, h))
        surface.blit(
            canvas,
            self._pan_x,
            self._pan_y,
            surface.width,
            surface.height,
            0,
            0,
        )
        self._draw_overflow_marks(surface)

    def _draw_overflow_marks(self, surface: Surface) -> None:
        """Mark each edge that has content past it.

        Without these a window onto a larger canvas looks like all there is.
        """
        content_w, content_h = self._content_size
        vw, vh = surface.width, surface.height
        mid_row, mid_col = vh // 2, vw // 2
        for row, col, mark, overflowing in (
            (mid_row, 0, _MARK_LEFT, self._pan_y > 0),
            (mid_row, vw - 1, _MARK_RIGHT, self._pan_y + vw < content_w),
            (0, mid_col, _MARK_UP, self._pan_x > 0),
            (vh - 1, mid_col, _MARK_DOWN, self._pan_x + vh < content_h),
        ):
            if overflowing:
                surface.draw_text_rgb(
                    row, col, mark, fg=DEFAULT_FG_DIM, bg=None
                )

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Wheel events pan the window; block-local clicks are not routed."""
        if event.kind is not MouseKind.PRESS:
            return False
        if event.button is MouseButton.WHEEL_LEFT:
            self.pan_by(cols=-PAN_STEP)
            return True
        if event.button is MouseButton.WHEEL_RIGHT:
            self.pan_by(cols=PAN_STEP)
            return True
        if event.button is MouseButton.WHEEL_UP:
            self.pan_by(rows=-PAN_STEP)
            return True
        if event.button is MouseButton.WHEEL_DOWN:
            self.pan_by(rows=PAN_STEP)
            return True
        return False


def _new_surface(width: int, height: int) -> Surface:
    """A fresh root surface to lay blocks onto before blitting the window."""
    return Surface(width, height)
