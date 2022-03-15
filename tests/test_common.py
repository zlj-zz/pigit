# -*- coding:utf-8 -*-
import pytest
import doctest
from unittest.mock import patch

import pigit.common.utils
from pigit.common.utils import traceback_info, get_current_shell, confirm


def test_doctest():
    doctest.testmod(pigit.common.utils, verbose=True)


def test():
    try:
        _ = int("abcd")
    except Exception:
        print(traceback_info("here is extra msg."))

    # when no traceback
    assert traceback_info() == ""


def test_1():
    print(get_current_shell())


@pytest.mark.parametrize(
    ["input_value", "return_bool"],
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
