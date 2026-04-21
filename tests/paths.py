# -*- coding: utf-8 -*-
"""Stable path constants for test modules (including nested test packages)."""

import os

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_PATH = _TESTS_DIR
PROJECT_ROOT = os.path.dirname(_TESTS_DIR)

TEST_CONFIG = f"{TEST_PATH}/pigit.toml"
