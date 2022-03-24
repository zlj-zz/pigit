# -*- coding:utf-8 -*-

from typing import TYPE_CHECKING, Dict, List, Optional, Union
from dataclasses import dataclass, field

# from . import box
from .box import Box, HEAVY_HEAD
from .style import Style
from .segment import Segment
from .ratio import ratio_reduce
from ._loop import loop_first_last, loop_last

if TYPE_CHECKING:
    from .console import Console


@dataclass
class BaseTb:
    """A base class of all table class."""

    title: Optional[str] = ""
    caption: Optional[str] = ""
    box: Box = HEAVY_HEAD
    width: Optional[int] = None
    show_edge: bool = True
    show_lines: bool = False
    show_header: bool = True
    title_style: Optional[str] = None
    caption_style: Optional[str] = None
    border_style: Optional[str] = None

    def _collapse_widths(
        self, widths: List[int], wrapable: List[bool], max_width: int
    ) -> List[int]:
        """Reduce widths so that the total is under max_width.

        Args:
            widths (List[int]): List of widths.
            wrapable (List[bool]): List of booleans that indicate if a column may shrink.
            max_width (int): Maximum width to reduce to.

        Returns:
            List[int]: A new list of widths.
        """

        total_width = sum(widths)
        excess_width = total_width - max_width

        if any(wrapable):
            while total_width and excess_width > 0:
                max_column = max(
                    width for width, allow_wrap in zip(widths, wrapable) if allow_wrap
                )
                second_max_column = max(
                    width if allow_wrap and width != max_column else 0
                    for width, allow_wrap in zip(widths, wrapable)
                )
                column_difference = max_column - second_max_column

                ratios = [
                    (1 if (width == max_column and allow_wrap) else 0)
                    for width, allow_wrap in zip(widths, wrapable)
                ]
                if not any(ratios) or not column_difference:
                    break
                max_reduce = [min(excess_width, column_difference)] * len(widths)
                widths = ratio_reduce(excess_width, ratios, max_reduce, widths)

                total_width = sum(widths)
                excess_width = total_width - max_width

        return widths

    def set_shape(self, height: int, lines: List, width: int) -> List[Segment]:
        extra_lines = height - len(lines)
        blank = [Segment(" " * width)]
        shaped_lines = lines[:height]
        if extra_lines:
            shaped_lines = lines + [blank * extra_lines]

        return shaped_lines


@dataclass
class Column(object):
    _index: int = 0

    header: str = ""

    header_style: Union[str, Style] = ""

    style: Union[str, Style] = ""

    no_wrap: bool = False

    _cells: List = field(default_factory=list)


@dataclass
class Row:
    style: Union[str, Style] = ""

    end_section: bool = False


@dataclass
class Table(BaseTb):
    def __post_init__(self):
        self._columns: List[Column] = []
        self._rows: List[Row] = []

    @property
    def _extra_width(self):
        width = 0
        if self.box and self.show_edge:
            width += 2
        if self.box:
            width += len(self._columns) - 1

        return width

    def add_column(
        self,
        header,
        header_style: Optional[str] = "bold",
        style: Optional[str] = None,
        no_wrap: bool = False,
    ):
        column = Column(
            header=header,
            header_style=header_style,
            style=style,
            no_wrap=no_wrap,
            _index=len(self._columns),
        )

        self._columns.append(column)

    def add_row(self, *values, style: Optional[str] = None, end_section: bool = False):
        cells = values
        columns = self._columns

        if len(values) < len(columns):
            cells = [*cells, *[None] * len(columns) - len(values)]

        for idx, cell in enumerate(cells):
            if idx == len(columns):
                column = Column(_index=idx)
                for _ in self._rows:
                    column._cells.append("")
                columns.append(column)
            else:
                column = columns[idx]

            if cell is None:
                column._cells.append("")
            else:
                column._cells.append(cell)

        self._rows.append(Row(style=style, end_section=end_section))

    def get_row_style(self, console: "Console", index: int):
        """Get current row style."""

        style = Style.null()
        row_style = self._rows[index].style
        if row_style is not None:
            style += console.get_style(row_style)

        return style

    def _get_cells(self, console: "Console", column: Column):
        raw_cells = []

        if self.show_header:
            raw_cells.append(
                Segment(column.header, console.get_style(column.header_style or ""))
            )

        cell_style = console.get_style(column.style or "")
        raw_cells.extend(Segment(cell, cell_style) for cell in column._cells)
        return raw_cells

    def _measure_column(self, console: "Console", column: Column, max_width: int):
        if max_width < 1:
            return 0

        cells = self._get_cells(console, column)

        return max(cell.cell_len_without_tag for cell in cells)

    def _calc_column_widths(self, console: "Console", max_width: int):
        columns = self._columns

        widths = [
            self._measure_column(console, column, max_width) for column in columns
        ]

        table_width = sum(widths)

        if table_width > max_width:
            widths = self._collapse_widths(
                widths, [not column.no_wrap for column in columns], max_width
            )
            table_width = sum(widths)
            if table_width > max_width:
                excess_width = table_width - max_width
                widths = ratio_reduce(excess_width, [1] * len(widths), widths, widths)
                # table_width = sum(widths)

        return widths

    def _render(self, console: "Console", widths: List[int]):

        border_style = console.get_style(self.border_style or "")
        _columns_cells = [self._get_cells(console, column) for column in self._columns]
        row_cells = list(zip(*_columns_cells))

        columns = self._columns
        show_edge = self.show_edge
        show_lines = self.show_lines
        show_header = self.show_header

        _box = self.box.substitute(console) if self.box else None
        new_line = Segment.line()

        if _box:
            box_segments = [
                (
                    Segment(_box.head_left, border_style),
                    Segment(_box.head_right, border_style),
                    Segment(_box.head_vertical, border_style),
                ),
                (
                    Segment(_box.foot_left, border_style),
                    Segment(_box.foot_right, border_style),
                    Segment(_box.foot_vertical, border_style),
                ),
                (
                    Segment(_box.mid_left, border_style),
                    Segment(_box.mid_right, border_style),
                    Segment(_box.mid_vertical, border_style),
                ),
            ]
            if show_edge:
                yield Segment(_box.get_top(widths), border_style)
                yield new_line
        else:
            box_segments = []

        set_shape = self.set_shape
        get_row_style = self.get_row_style
        get_style = console.get_style

        for index, (first, last, row_cell) in enumerate(loop_first_last(row_cells)):
            header_row = first and show_header
            footer_row = last
            row = (
                self._rows[index - show_header]
                if (not header_row and not footer_row)
                else None
            )

            max_height = 1
            cells: List = []
            if header_row or footer_row:
                row_style = Style.null()
            else:
                row_style = get_style(
                    get_row_style(console, index - 1 if show_header else index)
                )

            for width, cell, column in zip(widths, row_cell, columns):
                lines = console.render_lines(
                    cell.text, width, style=cell.style + row_style
                )
                max_height = max(max_height, len(lines))
                cells.append(lines)

            row_height = max(len(cell) for cell in cells)

            cells[:] = [
                set_shape(max_height, cell, width) for width, cell in zip(widths, cells)
            ]

            if _box:
                left, right, _divider = box_segments[0 if first else (2 if last else 1)]

                # If the column divider is whitespace also style it with the row background
                divider = _divider
                for line_no in range(max_height):
                    if show_edge:
                        yield left
                    for last_cell, rendered_cell in loop_last(cells):
                        yield from rendered_cell[line_no]
                        if not last_cell:
                            yield divider
                    if show_edge:
                        yield right
                    yield new_line
            else:
                for line_no in range(max_height):
                    for rendered_cell in cells:
                        yield from rendered_cell[line_no]
                    yield new_line
            if _box and first and show_header:
                yield Segment(
                    _box.get_row(widths, "head", edge=show_edge), style=border_style
                )
                yield new_line
            end_section = row and row.end_section
            if _box and (show_lines or end_section):
                if (
                    not last
                    # and not (show_footer and index >= len(row_cells) - 2)
                    and not (show_header and header_row)
                ):
                    # yield Segment(
                    #     _box.get_row(widths, "mid", edge=show_edge), style=border_style
                    # )
                    yield Segment(
                        _box.get_row(widths, "row", edge=show_edge), style=border_style
                    )
                    yield new_line

        if _box and show_edge:
            yield Segment(_box.get_bottom(widths), style=border_style)
            yield new_line

    def __render__(self, console: "Console"):

        if not self._columns:
            yield Segment("\n")
            return

        max_width = console.width
        if self.width is not None:
            max_width = self.width

        extra_width = self._extra_width
        widths = self._calc_column_widths(console, max_width - extra_width)
        table_width = sum(widths) + extra_width

        def render_annotation(text, style):
            render_text = (
                console.render_str2(text, style=style)
                if isinstance(text, str)
                else text
            )
            return render_text

        if self.title:
            yield render_annotation(
                (table_width - len(self.title)) // 2 * " " + self.title + "\n",
                style=console.get_style(self.title_style or ""),
            )
        yield from self._render(console, widths)
        if self.caption:
            yield render_annotation(
                (table_width - len(self.caption)) // 2 * " " + self.caption + "\n",
                style=console.get_style(self.caption_style or ""),
            )


@dataclass
class Unit(object):
    _index: int = 0
    header: str = ""
    header_style: Union[str, Style] = ""
    kv: Dict = field(default_factory=dict)
    kv_style: Union[None, str, Style, List[Union[str, Style]]] = None

    def __post_init__(self):
        style = self.kv_style
        if style is None:
            self.kv_style = ["", ""]
        elif isinstance(style, (str, Style)):
            self.kv_style = [style, ""]
        elif isinstance(style, list) and len(style) < 2:
            self.kv_style.append("")

    def add_kv(self, key, value, cover: bool = False) -> bool:
        # sourcery skip: merge-duplicate-blocks
        if cover:
            self.kv[key] = value

        elif self.kv.get(key) is None:
            self.kv[key] = value

        else:
            return False

        return True


@dataclass
class UintTable(BaseTb):
    """

    table format:
        ┏━━━━━━━━━━━━━┓
        ┃ Fruit color ┃
        ┣━━━━━━┳━━━━━━┫
        ┃apple ┃red   ┃
        ┃grape ┃purple┃
        ┣━━━━━━┻━━━━━━┫
        ┃Animal color ┃
        ┣━━━━━━┳━━━━━━┫
        ┃cattle┃yellow┃
        ┃sheep ┃white ┃
        ┣━━━━━━┻━━━━━━┫
        ┃      ────END┃
        ┗━━━━━━━━━━━━━┛
    """

    def __post_init__(self) -> None:
        self.units: List[Unit] = []

    @property
    def _extra_width(self):
        width = 0
        if self.box and self.show_edge:
            width += 2
        if self.box:
            width += 1

        return width

    def add_unit(
        self,
        header: str,
        header_style: Union[str, Style] = None,
        values: Optional[Dict] = None,
        values_style: Union[None, str, Style, List[Union[str, Style]]] = None,
    ) -> Unit:
        if values is None:
            values = {}

        unit = Unit(
            header=header,
            header_style=header_style,
            kv=values,
            kv_style=values_style,
            _index=len(self.units),
        )
        self.units.append(unit)
        return unit

    def _measure_unit(self, console: "Console", unit: Unit, max_width: int):
        # TODO: process for chinese
        if max_width < 1:
            return (0, 0)

        header_len = len(unit.header)
        col1 = max(len(key) for key in unit.kv)
        col2 = max(len(value) for value in unit.kv.values())

        if header_len > col1 + col2:
            while True:
                col2 += 1
                if header_len <= col1 + col2:
                    break
                col1 += 1
                if header_len <= col1 + col2:
                    break

        return (col1, col2)

    def _calc_unit_widths(self, console: "Console", max_width: int):
        units = self.units

        width_range = [self._measure_unit(console, unit, max_width) for unit in units]
        col1 = col2 = 0
        for item in width_range:
            col1 = max(col1, item[0])
            col2 = max(col2, item[1])

        widths = [col1, col2]
        table_width = col1 + col2

        if table_width > max_width:
            widths = self._collapse_widths(widths, [True, True], max_width)
            table_width = sum(widths)
            if table_width > max_width:
                excess_width = table_width - max_width
                widths = ratio_reduce(excess_width, [1] * len(widths), widths, widths)
                # table_width = sum(widths)

        return widths

    def _render_line(
        self, cells, height, box_segments, show_edge, is_header: bool = False
    ):
        new_line = Segment.line()

        if box_segments:
            left, right, _divider = box_segments[
                # 0 if first else (2 if last else 1)
                0
                if is_header
                else 1
            ]

            # If the column divider is whitespace also style it with the row background
            divider = _divider
            for line_no in range(height):
                if show_edge:
                    yield left
                for last_cell, rendered_cell in loop_last(cells):
                    yield from rendered_cell[line_no]
                    if not last_cell:
                        yield divider
                if show_edge:
                    yield right
                yield new_line
        else:
            for line_no in range(height):
                for rendered_cell in cells:
                    yield from rendered_cell[line_no]
                yield new_line

    def _render(self, console: "Console", widths: List[int]):
        border_style = console.get_style(self.border_style or "")
        units = self.units
        # print(units)

        show_edge = self.show_edge
        show_lines = self.show_lines
        show_header = self.show_header

        _box = self.box.substitute(console) if self.box else None
        new_line = Segment.line()

        if _box:
            box_segments = [
                (
                    Segment(_box.head_left, border_style),
                    Segment(_box.head_right, border_style),
                    Segment(_box.head_vertical, border_style),
                ),
                (
                    Segment(_box.foot_left, border_style),
                    Segment(_box.foot_right, border_style),
                    Segment(_box.foot_vertical, border_style),
                ),
                (
                    Segment(_box.mid_left, border_style),
                    Segment(_box.mid_right, border_style),
                    Segment(_box.mid_vertical, border_style),
                ),
            ]
        else:
            box_segments = []

        get_style = console.get_style
        set_shape = self.set_shape

        for index, (first, last, unit) in enumerate(loop_first_last(units)):
            header_row = first and show_header
            footer_row = last

            if show_edge:
                if header_row:
                    yield Segment(_box.get_top(widths, merge=True), border_style)
                    yield new_line
                else:
                    yield Segment(
                        _box.get_row(widths, "head", edge=show_edge, cross_level="up"),
                        style=border_style,
                    )
                    yield new_line

            # yield one unit header
            header_style = get_style(unit.header_style or "")
            lines = console.render_lines(
                unit.header, sum(widths) + 1, style=header_style
            )
            max_height = len(lines)
            cells = [set_shape(max_height, lines, sum(widths) + 1)]
            yield from self._render_line(
                cells, max_height, box_segments, show_edge, is_header=True
            )
            yield Segment(
                _box.get_row(widths, "head", edge=show_edge, cross_level="down"),
                style=border_style,
            )
            yield new_line

            for row_cell in unit.kv.items():
                max_height = 1
                cells: List = []

                for width, cell, style in zip(widths, row_cell, unit.kv_style):
                    lines = console.render_lines(cell, width, style=get_style(style))
                    max_height = max(max_height, len(lines))
                    cells.append(lines)

                cells[:] = [
                    set_shape(max_height, cell, width)
                    for width, cell in zip(widths, cells)
                ]

                yield from self._render_line(cells, max_height, box_segments, show_edge)
                if _box and (show_lines):
                    yield Segment(
                        _box.get_row(widths, "row", edge=show_edge),
                        style=border_style,
                    )
                    yield new_line

        if _box and show_edge:
            yield Segment(_box.get_bottom(widths), style=border_style)
            yield new_line

    def __render__(self, console: "Console"):
        if not self.units:
            yield Segment.line()
            return

        max_width = console.width
        if self.width is not None:
            max_width = self.width

        extra_width = self._extra_width
        widths = self._calc_unit_widths(console, max_width - extra_width)
        # print(widths)
        table_width = sum(widths) + extra_width

        def render_annotation(text, style):
            render_text = (
                console.render_str2(text, style=style)
                if isinstance(text, str)
                else text
            )
            return render_text

        if self.title:
            yield render_annotation(
                (table_width - len(self.title)) // 2 * " " + self.title + "\n",
                style=console.get_style(self.title_style or ""),
            )
        yield from self._render(console, widths)
        if self.caption:
            yield render_annotation(
                (table_width - len(self.caption)) // 2 * " " + self.caption + "\n",
                style=console.get_style(self.caption_style or ""),
            )
