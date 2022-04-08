# -*- coding:utf-8 -*-
import pytest
import doctest
from unittest.mock import patch
from pprint import pprint

from pigit.common.utils import (
    traceback_info,
    confirm,
    async_run_cmd,
    exec_async_tasks,
)
from pigit.common.func import dynamic_default_attrs


def test_doctest():
    import pigit.common.utils

    doctest.testmod(pigit.common.utils, verbose=True)


def test_traceback_info():
    try:
        _ = int("abcd")
    except Exception:
        print(traceback_info("here is extra msg."))

    # when no traceback
    assert traceback_info() == ""


@pytest.mark.parametrize(
    ("input_value", "return_bool"),
    [
        ["", True],
        ["y", True],
        ["yes", True],
        ["n", False],
        ["no", False],
    ],
)
@patch("builtins.input")
def test_confirm(mock_input, input_value: str, return_bool: bool):
    mock_input.return_value = input_value
    assert confirm("confirm:") == return_bool


def test_async_cmd_func():
    print()

    code = """\
# -*- coding:utf-8 -*-

if __name__ == '__main__':
    import time

    print({0})
    time.sleep(int({0}))
    print({0})
"""
    tasks = [
        async_run_cmd(*["python3", "-c", code.format(i)], msg=f"msg {i}.")
        for i in range(5)
    ]
    pprint(tasks)
    result = exec_async_tasks(tasks)
    print(result)


class TestFunc:
    def test_dynamic_default_attrs(self):
        da = {"c": 3, "d": 4}
        f = dynamic_default_attrs(lambda a, b, c, d: (a, b, c, d), **da)

        assert f(1, 2) == (1, 2, 3, 4)
        assert f(1, 2, d=0) == (1, 2, 3, 0)
        # assert f(1, 2, 0) == (1, 2, 0, 4)

        def bp(a, b, c: int, d: int = 10):
            return (a, b, c, d)

        assert dynamic_default_attrs(bp, **da)(1, 2, 0) == (1, 2, 0, 4)
