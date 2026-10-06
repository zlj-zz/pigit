"""
Module: tests/termui/test_flow_board.py
Description: Tests for the wrapping, pannable block layout.
Author: Zev
Date: 2026-10-06
"""

from __future__ import annotations

import pytest

from pigit.termui import Component, Surface
from pigit.termui.containers import FlowBoard
from pigit.termui.containers.flow_board import COL_GAP, ROW_GAP, PAN_STEP
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind


class _Block(Component):
    """A block that fills its own box with one character."""

    def __init__(self, width: int, height: int, char: str) -> None:
        super().__init__()
        self._natural = (width, height)
        self.char = char

    @property
    def natural_size(self) -> tuple[int, int]:
        return self._natural

    def paint(self, surface: Surface) -> None:
        for row in range(surface.height):
            surface.draw_text_rgb(row, 0, self.char * surface.width)


def _board(*sizes: tuple[int, int], viewport: tuple[int, int]) -> tuple[FlowBoard, list]:
    blocks = [_Block(w, h, chr(ord("A") + i)) for i, (w, h) in enumerate(sizes)]
    board = FlowBoard(blocks)
    board.resize(viewport)
    return board, blocks


def _at(board: FlowBoard, char: str) -> tuple[int, int]:
    """Where *char* was placed, as ``(row, column)``."""
    for block, x, y in board._placements:
        if block.char == char:
            return (x, y)
    raise AssertionError(f"block {char} was not placed")


_MARKS = frozenset("‹›▲▼")


def _rows(
    board: FlowBoard, width: int, height: int, *, keep_marks: bool = False
) -> list[str]:
    """The board's rows; overflow marks blanked unless asked for."""
    surface = Surface(width, height)
    board.paint(surface)
    rows = ["".join(cell.char for cell in row) for row in surface._rows]
    if keep_marks:
        return rows
    return ["".join(" " if ch in _MARKS else ch for ch in row) for row in rows]


def test_blocks_share_one_row_while_they_fit():
    board, _ = _board((10, 3), (10, 3), viewport=(40, 10))
    assert _at(board, "A") == (0, 0)
    assert _at(board, "B") == (0, 10 + COL_GAP)
    assert board.content_size == (10 + COL_GAP + 10, 3)


def test_a_block_wraps_when_less_than_half_of_it_would_show():
    """The rule the layout is built on: half visible, or go to the next row."""
    board, _ = _board((10, 3), (10, 3), viewport=(16, 10))
    # 10 + COL_GAP = 12 leaves 4 columns, which is under half of 10.
    assert _at(board, "B") == (3 + ROW_GAP, 0)


def test_an_overhang_of_exactly_half_stays_on_the_row():
    """Half visible is enough to keep it; only *under* half wraps."""
    board, _ = _board((10, 3), (10, 3), viewport=(18, 10))
    assert _at(board, "B") == (0, 10 + COL_GAP)  # 18 - 12 == 6 == 10 / 2


def test_a_wrapped_block_is_drawn_below_not_to_the_right():
    """Pins the axis order: placements are (row, column), as Component.x/y are."""
    board, _ = _board((10, 3), (10, 3), viewport=(16, 10))
    rows = _rows(board, 16, 10)
    assert rows[0].startswith("A" * 10)
    assert rows[3 + ROW_GAP].startswith("B" * 10)


def test_a_block_wider_than_the_viewport_is_still_placed():
    """Wrapping must not loop forever on a block that can never fit."""
    board, _ = _board((30, 4), viewport=(10, 20))
    assert _at(board, "A") == (0, 0)
    assert board.content_size == (30, 4)


def test_every_row_gets_at_least_one_block():
    """The guard protects the first block of each row, not just the first."""
    board, _ = _board((40, 3), (40, 3), viewport=(10, 20))
    assert _at(board, "A") == (0, 0)
    assert _at(board, "B") == (3 + ROW_GAP, 0)


def test_content_width_has_no_trailing_gap():
    board, _ = _board((10, 3), (10, 3), viewport=(40, 10))
    assert board.content_size[0] == 10 + COL_GAP + 10


def test_a_row_is_as_tall_as_its_tallest_block():
    # 24 wide fits A + B (10 + gap + 10) and leaves too little for C.
    board, _ = _board((10, 3), (10, 7), (10, 3), viewport=(24, 40))
    assert _at(board, "A") == (0, 0)
    assert _at(board, "B") == (0, 10 + COL_GAP)
    assert _at(board, "C")[0] == 7 + ROW_GAP


def test_resize_relays_out():
    """Wrapping depends on the width, so a narrower board means more rows."""
    board, _ = _board((30, 3), (30, 3), viewport=(100, 20))
    assert board.content_size == (30 + COL_GAP + 30, 3)
    board.resize((40, 20))
    assert board.content_size == (30, 3 + ROW_GAP + 3)


def test_pan_is_clamped_to_the_content():
    board, _ = _board((100, 5), viewport=(40, 10))
    board.pan_by(rows=10_000, cols=10_000)
    # Wider than the window, not taller: the clamp follows each axis.
    assert board.pan == (0, 100 - 40)
    board.pan_by(rows=-10_000, cols=-10_000)
    assert board.pan == (0, 0)


def test_pan_home_returns_to_the_origin():
    board, _ = _board((100, 5), viewport=(40, 10))
    board.pan_by(cols=PAN_STEP)
    board.pan_home()
    assert board.pan == (0, 0)


def test_wheel_pans_in_both_axes():
    board, _ = _board((100, 50), viewport=(40, 10))

    def wheel(button: MouseButton) -> bool:
        return board.handle_mouse(MouseEvent(1, 1, button, MouseKind.PRESS))

    assert wheel(MouseButton.WHEEL_RIGHT) is True
    assert board.pan == (0, PAN_STEP)
    assert wheel(MouseButton.WHEEL_LEFT) is True
    assert board.pan == (0, 0)
    assert wheel(MouseButton.WHEEL_DOWN) is True
    assert board.pan == (PAN_STEP, 0)
    assert wheel(MouseButton.WHEEL_UP) is True
    assert board.pan == (0, 0)


def test_a_block_without_a_natural_size_is_refused():
    """Guessing a fallback would silently clip or hide the block."""

    class Sizeless(Component):
        def paint(self, surface):  # pragma: no cover - never reached
            pass

    board = FlowBoard([Sizeless()])
    with pytest.raises(ValueError, match="natural_size"):
        board.resize((40, 10))


def test_painting_a_block_that_scrolled_off_does_not_move_its_neighbours():
    """A window onto the canvas, not a rearranged row."""
    # 50 wide keeps both on one row (40 would wrap B) and is under the 62 the
    # two blocks need, so the right-hand one is only partly on screen.
    board, _ = _board((30, 3), (30, 3), viewport=(50, 10))
    assert _at(board, "A") == (0, 0)
    assert _at(board, "B") == (0, 30 + COL_GAP)
    assert board.content_size == (30 + COL_GAP + 30, 3)
    assert _rows(board, 50, 3)[0] == "A" * 30 + " " * COL_GAP + "B" * 18


def test_panning_down_reveals_the_rows_that_did_not_fit():
    board, _ = _board((50, 12), (50, 6), viewport=(40, 10))
    assert board.content_size == (50, 12 + ROW_GAP + 6)

    assert "B" not in "".join(_rows(board, 40, 10))
    board.pan_by(rows=12 + ROW_GAP)  # clamps to content_h - viewport_h
    assert "B" in "".join(_rows(board, 40, 10))


def test_mount_reaches_the_blocks():
    """Blocks are not framework children, so the board mounts them itself."""
    board, blocks = _board((10, 3), viewport=(40, 10))
    board.mount()
    try:
        assert all(block.is_mounted() for block in blocks)
    finally:
        board.unmount()
    assert not any(block.is_mounted() for block in blocks)


def test_overflow_marks_appear_only_where_content_continues():
    """Otherwise a window onto a larger canvas looks like all there is."""
    board, _ = _board((100, 40), viewport=(40, 10))

    at_origin = _rows(board, 40, 10, keep_marks=True)
    assert at_origin[5][0] != "‹" and at_origin[0][20] != "▲"
    assert at_origin[5][39] == "›" and at_origin[9][20] == "▼"

    board.pan_by(rows=5, cols=5)
    panned = _rows(board, 40, 10, keep_marks=True)
    assert panned[5][0] == "‹" and panned[0][20] == "▲"
    assert panned[5][39] == "›" and panned[9][20] == "▼"


def test_no_marks_when_everything_fits():
    board, _ = _board((30, 5), viewport=(40, 10))
    rows = _rows(board, 40, 10, keep_marks=True)
    assert not _MARKS & {char for row in rows for char in row}


class _Ruler(Component):
    """Numbers its own cells along one axis, so a pan is visible."""

    def __init__(self, width: int, height: int, *, axis: str) -> None:
        super().__init__()
        self._natural = (width, height)
        self._axis = axis

    @property
    def natural_size(self) -> tuple[int, int]:
        return self._natural

    def paint(self, surface: Surface) -> None:
        for row in range(surface.height):
            cells = range(surface.width)
            surface.draw_text_rgb(
                row,
                0,
                "".join(
                    str(((col if self._axis == "col" else row) // 10) % 10)
                    for col in cells
                ),
            )


def test_panning_right_shifts_the_window_not_the_blocks():
    """A window moves over the canvas; it does not re-lay the blocks out."""
    board = FlowBoard([_Ruler(100, 5, axis="col")])
    board.resize((40, 10))
    assert _rows(board, 40, 5)[0].startswith("0000000000")

    board.pan_by(cols=30)
    assert _rows(board, 40, 5)[0].startswith("3333333333")


def test_panning_down_shifts_the_window_vertically():
    board = FlowBoard([_Ruler(40, 100, axis="row")])
    board.resize((40, 10))
    assert _rows(board, 40, 10)[0].startswith("0000000000")

    board.pan_by(rows=30)
    assert _rows(board, 40, 10)[0].startswith("3333333333")


def test_a_relayout_keeps_the_block_the_window_was_looking_at():
    """Widening re-flows the blocks, and the clamp alone loses the one in view.

    Three 30x8 blocks stack one per row at 40 columns. Scrolled down to the
    middle one, then widened, the middle block moves onto the first row beside
    a neighbour -- and clamping the old offset would leave its top cut off.
    """
    board, blocks = _board((30, 8), (30, 8), (30, 8), viewport=(40, 12))
    assert [_at(board, char) for char in "ABC"] == [(0, 0), (9, 0), (18, 0)]

    board.pan_by(rows=9)  # the middle block fills the window
    assert board._visible_block() is blocks[1]

    board.resize((70, 12))
    assert [_at(board, char)[0] for char in "ABC"] == [0, 0, 9]
    assert board.pan[0] == 0, "the block in view keeps its top row"

    rows = _rows(board, 70, 12)
    assert rows[0].startswith("A" * 30 + " " * COL_GAP + "B" * 30)


def test_blocks_always_get_their_natural_size():
    """A smaller box makes some widgets vanish rather than clip, so never give one.

    The window is what limits what is on screen; the block is laid out at the
    size it asked for and the board blits a window over it.
    """
    board, blocks = _board((80, 6), (60, 4), viewport=(20, 10))
    assert board.content_size == (80, 6 + ROW_GAP + 4)
    for block in blocks:
        assert block._size == block.natural_size


def test_a_relayout_at_the_origin_stays_at_the_origin():
    """Nothing was chosen yet, so nothing should be chased."""
    board, _ = _board((60, 8), (68, 12), (30, 9), viewport=(240, 30))
    assert board.content_size == (60 + COL_GAP + 68 + COL_GAP + 30, 12)

    board.resize((100, 30))
    assert board.pan == (0, 0), "a window at the origin keeps showing the start"
