# -*- coding:utf-8 -*-

from typing import TYPE_CHECKING, Optional
from itertools import islice
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from . import box
from .segment import Segment
from .ratio import ratio_reduce
from ._loop import loop_first_last, loop_last, loop_first

if TYPE_CHECKING:
    from .console import Console


@dataclass
class Column(object):
    _index: int = 0

    header: str = ""

    header_style: str = ""

    style: str = ""

    no_wrap: bool = False

    _cells: list = field(default_factory=list)


@dataclass
class Row:
    style: str = ""

    end_section: bool = False


class Table:
    def __init__(
        self,
        title: Optional[str] = "",
        caption: Optional[str] = "",
        box: box.Box = box.HEAVY_HEAD,
        width: Optional[int] = None,
        show_edge: bool = True,
        title_style: Optional[str] = None,
        caption_style: Optional[str] = None,
        border_style: Optional[str] = None,
    ) -> None:
        self._columns: list[Column] = []
        self._rows: list[Row] = []

        self._title = title
        self._caption = caption
        self._box = box
        self.width = width

        self._show_edge: bool = show_edge

        self.title_style = title_style or ""
        self.caption_style = caption_style or ""
        self.border_style = border_style or ""

    @property
    def _extra_width(self):
        width = 0
        if self._box and self._show_edge:
            width += 2
        if self._box:
            width += len(self._columns) - 1

        return width

    def add_column(
        self,
        header,
        header_style: Optional[str] = None,
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

    def _measure_column(self, column: Column, max_width: int):
        if max_width < 1:
            return 0

        cells = self._get_cells(column)
        return max([sum(c.cell_len for c in cell) for cell in cells])

    def _collapse_widths(self, widths: list[int], wrapable: list[bool], max_width: int):
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

    def _calc_column_widths(self, max_width: int):
        columns = self._columns

        widths = [self._measure_column(column, max_width) for column in columns]

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

    def _get_cells(self, column: Column):
        raw_cells = []

        raw_cells.append([Segment(column.header)])

        for cell in column._cells:
            raw_cells.append([Segment(cell, column.style)])

        return raw_cells

    def _render(self, console: "Console", widths: list[int]):
        new_line = "\n"

        _columns_cells = [self._get_cells(column) for column in self._columns]
        row_cells = list(zip(*_columns_cells))
        # print(row_cells)

        columns = self._columns
        show_edge = self._show_edge

        _box = self._box

        if _box:
            box_segments = [
                (_box.head_left, _box.head_right, _box.head_vertical),
                (_box.foot_left, _box.foot_right, _box.foot_vertical),
                (_box.mid_left, _box.mid_right, _box.mid_vertical),
            ]
            if show_edge:
                yield _box.get_top(widths)
                yield new_line
        else:
            box_segments = []

        # print(box_segments)

        for index, (first, last, row_cell) in enumerate(loop_first_last(row_cells)):
            header_row = first
            footer_row = last
            row = self._rows[index] if (not header_row and not footer_row) else None
            # print(row_cell)

            def render_lines(console, width, cell):
                lines = list(
                    islice(Segment.split_and_crop_lines(cell, width), None, None)
                )
                return lines

            max_height = 1
            cells = []
            for width, cell, column in zip(widths, row_cell, columns):
                lines = render_lines(console, width, cell)
                # print(lines)
                max_height = max(max_height, len(lines))
                cells.append(lines)

            row_height = max(len(cell) for cell in cells)

            def set_shape(height, lines, width):
                extra_lines = height - len(lines)
                if not extra_lines:
                    lines = lines[:]
                else:
                    lines = lines[:height]

                blank = [" " * width]
                lines = lines + blank * extra_lines

                return lines

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
            if _box and first:
                yield _box.get_row(widths, "head", edge=show_edge)
                yield new_line
            end_section = row and row.end_section
            if _box and (end_section):
                if not last and not (index >= len(row_cells) - 2) and not (header_row):
                    yield new_line

        if _box and show_edge:
            yield _box.get_bottom(widths)
            yield new_line

    def __render__(self, console: "Console"):

        if not self._columns:
            yield Segment("\n")
            return

        max_width = console.width
        if self.width is not None:
            max_width = self.width

        extra_width = self._extra_width
        widths = self._calc_column_widths(max_width - extra_width)
        # print(widths)
        table_width = sum(widths) + extra_width

        def render_annotation(text, style):
            render_text = (
                console.render_str2(text, style=style)
                if isinstance(text, str)
                else text
            )
            return render_text

        if self._title:
            yield render_annotation(
                (table_width - len(self._title)) // 2 * " " + self._title + "\n",
                style=self.title_style,
            )
        yield from self._render(console, widths)
        if self._caption:
            yield render_annotation(self._caption + "\n", style=self.caption_style)
