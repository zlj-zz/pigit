# -*- coding:utf-8 -*-
import pytest
import doctest
import time
from unittest.mock import patch
from pprint import pprint

from pigit.ext.utils import traceback_info, confirm
from pigit.ext.func import time_it


def test_doctest():
    import pigit.ext.utils

    doctest.testmod(pigit.ext.utils, verbose=False)


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


class TestFunc:
    @pytest.mark.parametrize(
        "test_input, expected_output, expected_time_unit, msg",
        [
            (lambda x: x + 1, 2, "second", ""),
            (lambda _: time.sleep(1.2), None, "second", ""),
            (lambda x, y: x * y, 20, "second", "multiplication"),
        ],
    )
    # `capsys ` is a builtin fixture，like sys.stdout and sys.stderr.
    def test_time_it_happy_path(
        self, monkeypatch, capsys, test_input, expected_output, expected_time_unit, msg
    ):
        # Arrange
        decorated_function = time_it(test_input)

        # Act
        result = (
            decorated_function(2, 10)
            if "multiplication" in msg
            else decorated_function(1)
        )

        # Assert
        captured = capsys.readouterr()
        assert expected_output == result
        assert expected_time_unit in captured.out
