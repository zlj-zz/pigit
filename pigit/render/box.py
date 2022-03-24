from typing import Iterable, List, Literal, TYPE_CHECKING

from ._loop import loop_last

if TYPE_CHECKING:
    from .console import Console


class Box:
    """Defines characters to render boxes.

    ┌─┬┐ top
    │ ││ head
    ├─┼┤ head_row
    │ ││ mid
    ├─┼┤ row
    ├─┼┤ foot_row
    │ ││ foot
    └─┴┘ bottom

    Args:
        box (str): Characters making up box.
        ascii (bool, optional): True if this box uses ascii characters only. Default is False.
    """

    def __init__(self, box: str, *, ascii: bool = False) -> None:
        self._box = box
        self.ascii = ascii
        line1, line2, line3, line4, line5, line6, line7, line8 = box.splitlines()
        # top
        self.top_left, self.top, self.top_divider, self.top_right, _ = iter(line1)
        # head
        self.head_left, _, self.head_vertical, self.head_right, _ = iter(line2)
        # head_row
        (
            self.head_row_left,
            self.head_row_horizontal,
            self.head_row_cross,
            self.head_row_right,
            self.head_row_up_cross,
            self.head_row_down_cross,
            _,
        ) = iter(line3)

        # mid
        self.mid_left, _, self.mid_vertical, self.mid_right, _ = iter(line4)
        # row
        self.row_left, self.row_horizontal, self.row_cross, self.row_right, _ = iter(
            line5
        )
        # foot_row
        (
            self.foot_row_left,
            self.foot_row_horizontal,
            self.foot_row_cross,
            self.foot_row_right,
            _,
        ) = iter(line6)
        # foot
        self.foot_left, _, self.foot_vertical, self.foot_right, _ = iter(line7)
        # bottom
        self.bottom_left, self.bottom, self.bottom_divider, self.bottom_right, _ = iter(
            line8
        )

    def __repr__(self) -> str:
        return "Box(...)"

    def __str__(self) -> str:
        return self._box

    def substitute(self, console: "Console") -> "Box":
        box = self
        if console.system == "Windows":
            box = WINDOWS_SUBSTITUTIONS.get(box, box)
        if not console.encoding.startswith("utf"):
            box = ASCII

        return box

    def get_top(self, widths: Iterable[int], merge: bool = False) -> str:
        """Get the top of a simple box.

        Args:
            widths (List[int]): Widths of columns.

        Returns:
            str: A string of box characters.
        """

        parts: List[str] = []
        append = parts.append
        append(self.top_left)
        for last, width in loop_last(widths):
            append(self.top * width)
            if not last:
                if merge:
                    append(self.top)
                else:
                    append(self.top_divider)
        append(self.top_right)
        return "".join(parts)

    def get_row(
        self,
        widths: Iterable[int],
        level: Literal["head", "row", "foot", "mid"] = "row",
        edge: bool = True,
        cross_level: Literal["mid", "up", "down"] = "mid",
    ) -> str:
        """Get the top of a simple box.

        Args:
            width (List[int]): Widths of columns.

        Returns:
            str: A string of box characters.
        """
        if level == "head":
            left = self.head_row_left
            horizontal = self.head_row_horizontal
            right = self.head_row_right
            if cross_level == "up":
                cross = self.head_row_up_cross
            elif cross_level == "down":
                cross = self.head_row_down_cross
            else:
                cross = self.head_row_cross
        elif level == "row":
            left = self.row_left
            horizontal = self.row_horizontal
            right = self.row_right
            cross = self.row_cross
        elif level == "mid":
            left = self.mid_left
            horizontal = " "
            cross = self.mid_vertical
            right = self.mid_right
        elif level == "foot":
            left = self.foot_row_left
            horizontal = self.foot_row_horizontal
            cross = self.foot_row_cross
            right = self.foot_row_right
        else:
            raise ValueError("level must be 'head', 'row' or 'foot'")

        parts: List[str] = []
        append = parts.append
        if edge:
            append(left)
        for last, width in loop_last(widths):
            append(horizontal * width)
            if not last:
                append(cross)
        if edge:
            append(right)
        return "".join(parts)

    def get_bottom(self, widths: Iterable[int]) -> str:
        """Get the bottom of a simple box.

        Args:
            widths (List[int]): Widths of columns.

        Returns:
            str: A string of box characters.
        """

        parts: List[str] = []
        append = parts.append
        append(self.bottom_left)
        for last, width in loop_last(widths):
            append(self.bottom * width)
            if not last:
                append(self.bottom_divider)
        append(self.bottom_right)
        return "".join(parts)


# flake8: noqa
# yapf: disable

ASCII: Box = Box(
    """\
+--+.
| ||.
|-+|--.
| ||.
|-+|.
|-+|.
| ||.
+--+.
""",
    ascii=True,
)

ASCII2: Box = Box(
    """\
+-++.
| ||.
+-++++.
| ||.
+-++.
+-++.
| ||.
+-++.
""",
    ascii=True,
)

ASCII_DOUBLE_HEAD: Box = Box(
    """\
+-++.
| ||.
+=++++.
| ||.
+-++.
+-++.
| ||.
+-++.
""",
    ascii=True,
)

SQUARE: Box = Box(
    """\
┌─┬┐.
│ ││.
├─┼┤┴┬.
│ ││.
├─┼┤.
├─┼┤.
│ ││.
└─┴┘.
"""
)

SQUARE_DOUBLE_HEAD: Box = Box(
    """\
┌─┬┐.
│ ││.
╞═╪╡╧╤.
│ ││.
├─┼┤.
├─┼┤.
│ ││.
└─┴┘.
"""
)

MINIMAL: Box = Box(
    """\
  ╷ .
  │ .
╶─┼╴┴┬.
  │ .
╶─┼╴.
╶─┼╴.
  │ .
  ╵ .
"""
)


MINIMAL_HEAVY_HEAD: Box = Box(
    """\
  ╷ .
  │ .
╺━┿╸┷┯.
  │ .
╶─┼╴.
╶─┼╴.
  │ .
  ╵ .
"""
)

MINIMAL_DOUBLE_HEAD: Box = Box(
    """\
  ╷ .
  │ .
 ═╪ ╧╤.
  │ .
 ─┼ .
 ─┼ .
  │ .
  ╵ .
"""
)


SIMPLE: Box = Box(
    """\
    .
    .
 ── ──.
    .
    .
 ── .
    .
    .
"""
)

SIMPLE_HEAD: Box = Box(
    """\
    .
    .
 ── ──.
    .
    .
    .
    .
    .
"""
)


SIMPLE_HEAVY: Box = Box(
    """\
    .
    .
 ━━ ━━.
    .
    .
 ━━ .
    .
    .
"""
)


HORIZONTALS: Box = Box(
    """\
 ── .
    .
 ── ──.
    .
 ── .
 ── .
    .
 ── .
"""
)

ROUNDED: Box = Box(
    """\
╭─┬╮.
│ ││.
├─┼┤┴┬.
│ ││.
├─┼┤.
├─┼┤.
│ ││.
╰─┴╯.
"""
)

HEAVY: Box = Box(
    """\
┏━┳┓.
┃ ┃┃.
┣━╋┫┻┳.
┃ ┃┃.
┣━╋┫.
┣━╋┫.
┃ ┃┃.
┗━┻┛.
"""
)

HEAVY_EDGE: Box = Box(
    """\
┏━┯┓.
┃ │┃.
┠─┼┨┴┬.
┃ │┃.
┠─┼┨.
┠─┼┨.
┃ │┃.
┗━┷┛.
"""
)

HEAVY_HEAD: Box = Box(
    """\
┏━┳┓.
┃ ┃┃.
┡━╇┩┻┯.
│ ││.
├─┼┤.
├─┼┤.
│ ││.
└─┴┘.
"""
)

DOUBLE: Box = Box(
    """\
╔═╦╗.
║ ║║.
╠═╬╣╩╦.
║ ║║.
╠═╬╣.
╠═╬╣.
║ ║║.
╚═╩╝.
"""
)

DOUBLE_EDGE: Box = Box(
    """\
╔═╤╗.
║ │║.
╟─┼╢┴┬.
║ │║.
╟─┼╢.
╟─┼╢.
║ │║.
╚═╧╝.
"""
)

# Map Boxes that don't render with raster fonts on to equivalent that do
WINDOWS_SUBSTITUTIONS = {
    ROUNDED: SQUARE,
    MINIMAL_HEAVY_HEAD: MINIMAL,
    SIMPLE_HEAVY: SIMPLE,
    HEAVY: SQUARE,
    HEAVY_EDGE: SQUARE,
    HEAVY_HEAD: SQUARE,
}
