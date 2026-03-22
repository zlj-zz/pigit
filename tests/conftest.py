# -*- coding:utf-8 -*-
import os
import sys

from .paths import PROJECT_ROOT, TEST_PATH  # noqa: E402

# Add source environment (package under test).
sys.path.insert(0, TEST_PATH)
sys.path.insert(0, PROJECT_ROOT)

_PIGIT_PATH = PROJECT_ROOT

# Not support.
if sys.platform == "win32":
    collect_ignore_glob = ["**/test_tui_input.py", "**/test_tui_eventloop.py"]

PYTHON_VERSION = sys.version_info[:3]
if PYTHON_VERSION < (3, 8, 5):
    raise Exception(
        "The current version of pigit does not support less than (Python3.8)."
    )


# /opt/homebrew/opt/python@3.8/bin/python3 -m pytest
