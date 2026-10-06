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
from ..surface import Surface

# Space between two blocks on a row, and between rows.
COL_GAP = 2
ROW_GAP = 1
# Columns or rows moved per mouse-wheel tick.
PAN_STEP = 5


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
        super().resize(size)
        self._relayout()

    def _relayout(self) -> None:
        """Place every block for the current width, then keep the pan in range.

        The layout depends on the board's *width*, not on the canvas width it
        produced last time: a block can only wrap once there is somewhere to
        wrap to. So a resize can both move blocks and shrink the canvas.

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
        self._clamp_pan()

    def _clamp_pan(self) -> None:
        """Keep the window inside the canvas."""
        content_w, content_h = self._content_size
        self._pan_x = max(0, min(self._pan_x, content_w - self._size[0]))
        self._pan_y = max(0, min(self._pan_y, content_h - self._size[1]))

    def pan_by(self, dx: int = 0, dy: int = 0) -> None:
        """Move the window, stopping at the canvas edges."""
        self._pan_x += dx
        self._pan_y += dy
        self._clamp_pan()

    def pan_home(self) -> None:
        """Return the window to the canvas origin."""
        self._pan_x = 0
        self._pan_y = 0

    def paint(self, surface: Surface) -> None:
        canvas = _new_surface(*self._content_size)
        for block, x, y in self._placements:
            w, h = block._size
            if w <= 0 or h <= 0:
                continue
            block.paint(canvas.subsurface(x, y, w, h))
        surface.blit(
            canvas,
            self._pan_y,
            self._pan_x,
            surface.width,
            surface.height,
            0,
            0,
        )

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Wheel events pan the window; block-local clicks are not routed."""
        if event.kind is not MouseKind.PRESS:
            return False
        if event.button is MouseButton.WHEEL_LEFT:
            self.pan_by(dx=-PAN_STEP)
            return True
        if event.button is MouseButton.WHEEL_RIGHT:
            self.pan_by(dx=PAN_STEP)
            return True
        if event.button is MouseButton.WHEEL_UP:
            self.pan_by(dy=-PAN_STEP)
            return True
        if event.button is MouseButton.WHEEL_DOWN:
            self.pan_by(dy=PAN_STEP)
            return True
        return False


def _new_surface(width: int, height: int) -> Surface:
    """A fresh root surface to lay blocks onto before blitting the window."""
    return Surface(width, height)
