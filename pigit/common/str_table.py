# -*- coding:utf-8 -*-

from copy import deepcopy

from .style import Symbol
from .escape import Fx


class baseTable(object):

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
        self.create_table()

    def __str__(self):
        if getattr(self, "table_str_list"):
            return "\n".join(self.table_str_list)
        else:
            return ""

    def _try_append_title(self):
        if self.title:
            line_max = sum(self.each_max) + len(self.each_max) + 1
            _t = "{}{:^%s}{}" % line_max
            self.table_str_list.append(_t.format(Fx.b, self.title, Fx.ub))

    def fix_data(self):
        raise NotImplementedError()

    def create_table(self):
        raise NotImplementedError()

    def print(self):
        for each in self.table_str_list:
            print(each)


class Table(baseTable):
    """Create a table from list.

    data format:
        title = ["name", "age", "gender"]
        data = [
            ["bob", "20", "f"],
            ["tom", "19", "f"],
        ]

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
        data: list,
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

        super().__init__(frame_format, nil, title=title)

    def fix_data(self):
        self.header_len = header_len = len(self.header)
        self.each_max = each_max = [len(i) for i in self.header]

        for item in self.data:
            # Complete missing element.
            item_len = len(item)
            if item_len < header_len:
                item.extend([self.nil] * (header_len - item_len))
            # Calc each max.
            for i, x in enumerate(item):
                x_len = len(Fx.pure(x))
                each_max[i] = max(each_max[i], x_len)

    def create_table(self):
        each_max = self.each_max
        rune = self.rune

        _t = "%s{:<%s}"
        _template = (
            "".join([_t % (self.rune[1], number) for number in each_max]) + rune[1]
        )

        _head = [
            rune[2] + rune[-3].join([rune[0] * i for i in each_max]) + rune[3],
            _template.format(*self.header),
            rune[6] + rune[-1].join([rune[0] * i for i in each_max]) + rune[7],
        ]

        _body = [_template.format(*item) for item in self.data]

        _foot = rune[4] + rune[-2].join([rune[0] * i for i in each_max]) + rune[5]

        self.table_str_list = []
        self._try_append_title()
        self.table_str_list.extend(_head)
        self.table_str_list.extend(_body)
        self.table_str_list.append(_foot)


class dTable(baseTable):
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

        max_core_len = 0

        for core, sub_dict in self.data.items():
            max_core_len = max(max_core_len, len(core))
            for k, v in sub_dict.items():
                each_max[0] = max(each_max[0], len(Fx.pure(k)))
                each_max[1] = max(each_max[1], len(Fx.pure(v)))

        # for Ensure that the table is output correctly when the len of sub title
        # bigger than the len of item.
        sum_each_max = sum(each_max)
        if max_core_len > sum_each_max:
            each_max[1] += max_core_len - sum_each_max

        self.line_max = sum(each_max) + len(each_max) + 1

    def create_table(self):
        rune = self.rune
        each_max = self.each_max
        line_max = self.line_max

        tb = self.table_str_list = []
        self._try_append_title()

        _core_template = "%(flag)s{:^%(number)s}%(flag)s" % {
            "flag": rune[1],
            "number": line_max - 2,
        }
        _item_template = "%(flag)s{:<%(num1)s}%(flag)s{:<%(num2)s}%(flag)s" % {
            "flag": rune[1],
            "num1": each_max[0],
            "num2": each_max[1],
        }
        _end_template = "%(flag)s{:>%(number)s}%(flag)s" % {
            "flag": rune[1],
            "number": line_max - 2,
        }

        tb.append(rune[2] + rune[0] * (line_max - 2) + rune[3])

        for key, sub_dict in self.data.items():
            tb.append(_core_template.format(key))
            tb.append(
                rune[6] + rune[-3].join([rune[0] * i for i in each_max]) + rune[7]
            )
            for k, v in sub_dict.items():
                tb.append(_item_template.format(k, v))
            tb.append(
                rune[6] + rune[-2].join([rune[0] * i for i in each_max]) + rune[7]
            )

        tb.append(_end_template.format("────END"))
        tb.append(rune[4] + rune[0] * (line_max - 2) + rune[5])
