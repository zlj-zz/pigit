import sys

sys.path.insert(0, ".")

import time
import textwrap
import pytest

from pigit.common.str_table import Table, dTable


@pytest.mark.parametrize(
    "title, data",
    [
        (
            ["name", "age", "gender"],
            [
                ["bob", "20", "f"],
                ["tom", "19", "f"],
            ],
        ),
        (
            ["name", "age", "gender"],
            [
                ["bob", "20", "f"],
                ["tom", "19"],
            ],
        ),
    ],
)
def test_table1(title, data):
    print()
    table = Table(title, data)
    table.print()


@pytest.mark.parametrize(
    "d_data",
    [
        {
            "Fruit color": {
                "apple": "red",
                "grape": "purple",
            },
            "Animal color": {
                "cattle": "yellow",
                "sheep": "white",
            },
        },
    ],
)
def test_table2(d_data):
    print()
    table = dTable(d_data)
    table.print()
