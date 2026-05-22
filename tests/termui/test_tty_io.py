"""
Module: tests/termui/test_tty_io.py
Description: Tests for TTY I/O helpers.
Author: Zev
Date: 2026-05-20
"""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from pigit.termui.tty_io import tty_ok, terminal_size, truncate_line


class TestTtyOk:
    def test_both_tty_returns_true(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=True):
            with mock.patch.object(sys.stdout, "isatty", return_value=True):
                assert tty_ok() is True

    def test_stdin_not_tty_returns_false(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            with mock.patch.object(sys.stdout, "isatty", return_value=True):
                assert tty_ok() is False

    def test_stdout_not_tty_returns_false(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=True):
            with mock.patch.object(sys.stdout, "isatty", return_value=False):
                assert tty_ok() is False


class TestTerminalSize:
    def test_returns_tuple(self):
        cols, rows = terminal_size()
        assert isinstance(cols, int)
        assert isinstance(rows, int)
        assert cols >= 20
        assert rows >= 1

    def test_oserror_fallback(self):
        with mock.patch("shutil.get_terminal_size", side_effect=OSError):
            assert terminal_size() == (80, 24)


class TestTruncateLine:
    def test_short_text_unchanged(self):
        assert truncate_line("hello", 10) == "hello"

    def test_zero_max_cols(self):
        assert truncate_line("hello", 0) == ""

    def test_negative_max_cols(self):
        assert truncate_line("hello", -1) == ""

    def test_truncates_long(self):
        result = truncate_line("hello world", 5)
        assert len(result) <= 5
        assert "…" in result

    def test_strips_newlines(self):
        assert truncate_line("a\nb\nc", 10) == "a b c"

    def test_max_cols_one(self):
        result = truncate_line("hello", 1)
        # truncate_by_width returns the first character when max_cols=1
        assert len(result) == 1
