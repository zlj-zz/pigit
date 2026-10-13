# -*- coding:utf-8 -*-
import os
import sys

import pytest

from .paths import PROJECT_ROOT, TEST_PATH  # noqa: E402

# Add source environment (package under test).
sys.path.insert(0, TEST_PATH)
sys.path.insert(0, PROJECT_ROOT)

_PIGIT_PATH = PROJECT_ROOT

# Not support.
if sys.platform == "win32":
    collect_ignore_glob = ["**/test_tui_input.py", "**/test_termui_eventloop.py"]

PYTHON_VERSION = sys.version_info[:3]
if PYTHON_VERSION < (3, 11):
    raise Exception(
        "The current version of pigit does not support less than Python 3.11."
    )


@pytest.fixture(autouse=True)
def clipboard(monkeypatch) -> list[str]:
    """Keep tests off the system clipboard; collect what would have been copied.

    The app copies every error toast there, so a test that drives a real
    ``PigitApplication`` into a failure toast would overwrite the clipboard of
    whoever is running the suite. Tests that assert on it take this fixture.
    """
    copied: list[str] = []

    def _copy(text: str) -> bool:
        copied.append(text)
        return True

    monkeypatch.setattr("pigit.app.copy_to_clipboard", _copy)
    yield copied
