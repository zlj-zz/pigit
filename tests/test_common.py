# -*- coding:utf-8 -*-
import pytest
import doctest
from unittest.mock import patch
from pprint import pprint

import pigit.common.utils
from pigit.common.utils import (
    traceback_info,
    get_current_shell,
    confirm,
    async_run_cmd,
    exec_async_tasks,
)


def test_doctest():
    doctest.testmod(pigit.common.utils, verbose=True)


def test_traceback_info():
    try:
        _ = int("abcd")
    except Exception:
        print(traceback_info("here is extra msg."))

    # when no traceback
    assert traceback_info() == ""


def test_1():
    print(get_current_shell())


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
