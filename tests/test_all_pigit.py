# -*- coding:utf-8 -*-
import pytest
from .utils import analyze_it

import pigit.entry as entry_mod
from pigit.entry import pigit


@pytest.fixture(autouse=True)
def _ensure_pigit_context():
    """Re-attach context: collection may import entry before test_context detach clears ContextVar."""
    entry_mod.Context.install(entry_mod.ctx)
    yield


@pytest.mark.parametrize(
    "command",
    [
        "--report",
        "--config",  # git config
        "--information",  # git information
        "--count",  # code counter
        "cmd",
        "cmd -l",
        "cmd -t",
        "cmd -t Branch",
        "cmd ws",
        "repo ll",
    ],
)
def test_color_command(command: str):
    print()
    pigit(command.split())
