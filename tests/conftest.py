# -*- coding:utf-8 -*-
import os
import sys

# Add source environment.
_PIGIT_PATH = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _PIGIT_PATH)

TEST_PATH = os.path.dirname(__file__)

# Not support.
if sys.platform == "win32":
    collect_ignore_glob = ["test_tui_input.py", "test_tui_eventloop.py"]

PYTHON_VERSION = sys.version_info[:3]
if PYTHON_VERSION < (3, 8, 5):
    raise Exception(
        "The current version of pigit does not support less than (Python3.8)."
    )


# /opt/homebrew/opt/python@3.8/bin/python3 -m pytest
