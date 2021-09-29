import time
import textwrap
import pytest

from pigit.common.str_table import Table, dTable


@pytest.mark.parametrize(
    "header, data, title",
    [
        (
            ["name", "age", "gender"],
            [
                ["bob", "20", "f"],
                ["tom", "19", "f"],
            ],
            "Student",
        ),
        (
            ["name", "age", "gender"],
            [
                ["bob", "20", "\033[31;1mf\033[0m"],
                ["tom", "19", "f"],
            ],
            "Has missing",
        ),
        (
            ["name", "age", "gender"],
            [
                ["bob", "20", "f"],
                ["tom", "19"],
            ],
            "",
        ),
        (
            ["名字", "年龄", "性别"],
            [
                ["张三", "20", "f"],
                ["李四", "19", "f"],
            ],
            "",
        ),
    ],
)
def test_table1(header, data, title):
    print()
    table = Table(header, data, title)
    table.print()
    print(table.each_column_width)
    # print(table)


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
        {
            "水果颜色": {
                "苹果": "红色",
                "葡萄": "紫色",
            },
        },
    ],
)
def test_table2(d_data):
    print()
    table = dTable(d_data)
    table.print()
