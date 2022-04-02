# -*- coding:utf-8 -*-
import pytest
from .utils import analyze_it

from pigit.entry import pigit


@pytest.mark.parametrize(
    "command",
    [
        "--report",
        "--config",  # git config
        "--information",  # git information
        "--count",  # code counter
        "--create-config",
        "cmd",
        "cmd -s",
        "cmd -t",
        "cmd -p branch",
        "cmd ws",
        "cmd -t",
        "repo ll",
    ],
)
def test_color_command(command: str):
    print()
    pigit(command.split())
