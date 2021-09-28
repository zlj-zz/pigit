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
        {
            "File suffixes for some languages": {
                "C": "c",
                "C#": "csharp",
                "Python": "py",
                "JavaScript": "js",
            },
        },
        {
            "Fruit color": {
                "apple": "\033[31mred\033[0m",
                "grape": "purple",
            },
        },
    ],
)
def test_table2(d_data):
    print()
    table = dTable(d_data)
    table.print()
