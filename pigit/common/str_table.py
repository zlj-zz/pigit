# -*- coding:utf-8 -*-

from copy import deepcopy
from typing import Generator

from .style import Symbol
from .escape import Fx
from .str_utils import get_width


# XXX: Contains non-string data <zlj-zz>
class _baseTable(object):

    """Docstring for baseTable."""

    table_str_list: list
    each_max: list

    def __init__(self, frame_format: str, nil: str, title: str = ""):
        if frame_format not in Symbol.rune.keys():
            frame_format = "bold"
        self.rune = Symbol.rune[frame_format]
        self.nil = nil
        self.title = title

        # create table when init.
        self.fix_data()

    def _append_title(self) -> str:
        if self.title:
            line_max = sum(self.each_max) + len(self.each_max) + 1
            _t = "{}{:^%s}{}" % line_max
            return _t.format(Fx.b, self.title, Fx.ub)
        return "\r"

    def real_len(self, text: str):
        return sum([get_width(ord(ch)) for ch in text])

    def fix_data(self):
        raise NotImplementedError()

    def generate_table(self) -> Generator:
        raise NotImplementedError()

    def print(self) -> None:
        print(self._append_title())

        g = self.generate_table()
        for i in g:
            print(i, end="")


class Table(_baseTable):
    """Create a table from list.

    data format:
        header = ["name", "age", "gender"]
        data = [
            ["bob", "20", "f"],
            ["tom", "19", "f"],
        ]
        tb = Table(header, data)
        tb.print()

    table format:
        ┏━━━━┳━━━┳━━━━━━┓
        ┃name┃age┃gender┃
        ┣━━━━╋━━━╋━━━━━━┫
        ┃bob ┃20 ┃f     ┃
        ┃tom ┃19 ┃f     ┃
        ┗━━━━┻━━━┻━━━━━━┛

    """

    def __init__(
        self,
        header: list,
        data: list[list],
        title: str = "",
        frame_format: str = "bold",
        nil: str = "",
    ):
        # Check data.
        if not isinstance(header, list):
            raise TypeError("title need is a list.")
        self.header = deepcopy(header)

        # Check data.
        if not isinstance(data, list):
            raise TypeError("data need is a list.")
        for item in data:
            if not isinstance(item, list):
                raise TypeError("each item of data need is a list.")
        self.data = deepcopy(data)

        self.header_len = len(self.header)
        self.each_max = [self.real_len(i) for i in self.header]

        super().__init__(frame_format, nil, title=title)

    def fix_data(self):
        header_len = self.header_len

        for item in self.data:
            # Complete missing element.
            item_len = len(item)
            if item_len < header_len:
                item.extend([self.nil] * (header_len - item_len))
            elif item_len > header_len:
                item = item[0:header_len]
            # Calc each max.
            self._adjust_each_max(item)

    def add_row(self, row: list) -> None:
        # XXX: whether need deepcopy
        row_len = len(row)
        if row_len < self.header_len:
            row.extend([self.nil] * (self.header_len - row_len))
        elif row_len > self.header_len:
            row = row[0 : self.header_len]

        self._adjust_each_max(row)
        self.data.append(row)

    def _adjust_each_max(self, cells: list) -> None:
        for i, x in enumerate(cells):
            x_len = self.real_len(Fx.pure(x))
            self.each_max[i] = max(self.each_max[i], x_len)

    def generate_table(self) -> Generator:
        each_max = self.each_max
        rune = self.rune
        indexes = range(self.header_len)

        # top and title line.
        yield rune[2] + rune[-3].join([rune[0] * i for i in each_max]) + rune[3] + "\n"
        yield rune[1]
        for idx in indexes:
            width = each_max[idx]
            cell = self.header[idx]
            cell_len = self.real_len(Fx.pure(cell))
            yield cell + " " * (width - cell_len) + rune[1]
        yield "\n"
        yield rune[6] + rune[-1].join([rune[0] * i for i in each_max]) + rune[7] + "\n"

        # all rows.
        for cells in self.data:
            yield rune[1]
            for idx in indexes:
                width = each_max[idx]
                cell = cells[idx]
                cell_len = self.real_len(Fx.pure(cell))
                yield cell + " " * (width - cell_len) + rune[1]
            yield "\n"

        # bottom
        yield rune[4] + rune[-2].join([rune[0] * i for i in each_max]) + rune[5] + "\n"


class dTable(_baseTable):
    """Create table from a special format dict.

    d_data format: dict[str, dict[str, str]]
        d_data = {
            'Fruit color': {
                'apple': 'red',
                'grape': 'purple',
            },
            'Animal color': {
                'cattle': 'yellow',
                'sheep': 'white',
            },
        }

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

    def __init__(
        self, d_data: dict, title: str = "", frame_format: str = "bold", nil: str = ""
    ):
        # check data whether right.
        if not isinstance(d_data, dict):
            raise TypeError("d_data need is a dict.")
        for item in d_data.values():
            if not isinstance(item, dict):
                raise TypeError("the item of d_data need is a dict.")

        self.data = deepcopy(d_data)

        super().__init__(frame_format, nil, title=title)

    def fix_data(self):
        self.each_max = each_max = [0, 0]
        max_subtitle_len = 0
        r_len = self.real_len

        for subtitle, sub_dict in self.data.items():
            max_subtitle_len = max(max_subtitle_len, r_len(subtitle))
            for k, v in sub_dict.items():
                each_max[0] = max(each_max[0], r_len(Fx.pure(k)))
                each_max[1] = max(each_max[1], r_len(Fx.pure(v)))

        # for Ensure that the table is output correctly when the len of sub title
        # bigger than the len of item.
        sum_each_max = sum(each_max)
        if max_subtitle_len > sum_each_max:
            each_max[1] += max_subtitle_len - sum_each_max

        self.line_max = sum(each_max) + len(each_max) + 1

    def generate_table(self) -> Generator:
        rune = self.rune
        each_max = self.each_max
        line_max = self.line_max
        r_len = self.real_len

        _end_template = "%(flag)s{:>%(number)s}%(flag)s\n" % {
            "flag": rune[1],
            "number": line_max - 2,
        }

        sub_top = (
            f"{rune[6]}{rune[-3].join([rune[0] * i for i in each_max])}{rune[7]}\n"
        )
        sub_bottom = (
            f"{rune[6]}{rune[-2].join([rune[0] * i for i in each_max])}{rune[7]}\n"
        )

        # top
        yield f"{rune[2]}{rune[0]*(line_max-2)}{rune[3]}\n"

        for subtitle, sub_dict in self.data.items():
            # subtitle part
            yield rune[1]
            subtitle_len = r_len(Fx.pure(subtitle))
            _div, _mod = divmod(line_max - 2 - subtitle_len, 2)
            yield f"{_div * ' '}{subtitle}{(_div + _mod) * ' '}{rune[1]}\n"

            # sub dict
            yield sub_top
            for k, v in sub_dict.items():
                k_len = r_len(Fx.pure(k))
                yield rune[1] + k + (each_max[0] - k_len) * " " + rune[1]
                v_len = r_len(Fx.pure(v))
                yield v + (each_max[1] - v_len) * " " + rune[1] + "\n"
            yield sub_bottom

        # bottom
        yield _end_template.format("────END")
        yield f"{rune[4]}{rune[0] * (line_max - 2)}{rune[5]}\n"
