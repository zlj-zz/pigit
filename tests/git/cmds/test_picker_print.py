# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_picker_print.py
Description: Tests for cmd picker --pick-print and widget output.
Author: Zev
Date: 2026-04-15
"""

import sys

import pytest

from pigit.git.cmds._picker import run_cmd_new_picker
from pigit.handlers.cmd_handler import handle_widget


class TestPickerPrintOnly:
    def test_run_picker_print_only_no_tty(self, monkeypatch):
        """No tty returns error message for print_only too."""
        monkeypatch.setattr("pigit.git.cmds._picker._tty_ok", lambda: False)
        exit_code, message = run_cmd_new_picker(print_only=True)
        assert exit_code == 1
        assert "interactive terminal" in message.lower()


class TestWidgetOutput:
    def test_widget_bash_contains_binding(self, capsys):
        assert handle_widget("bash") == 0
        out = capsys.readouterr().out
        assert "_pigit_cmd_widget" in out
        assert "bind -x" in out
        assert "\\C-g" in out
        assert "PIGIT_WIDGET_OUTPUT" in out
        assert "/dev/tty" in out

    def test_widget_zsh_contains_binding(self, capsys):
        assert handle_widget("zsh") == 0
        out = capsys.readouterr().out
        assert "zle -N" in out
        assert "bindkey" in out
        assert "PIGIT_WIDGET_OUTPUT" in out
        assert "/dev/tty" in out

    def test_widget_fish_contains_binding(self, capsys):
        assert handle_widget("fish") == 0
        out = capsys.readouterr().out
        assert "__pigit_cmd_widget" in out
        assert "bind" in out
        assert "\\cg" in out
        assert "PIGIT_WIDGET_OUTPUT" in out
        assert "/dev/tty" in out

    def test_widget_unsupported(self, capsys):
        assert handle_widget("unknown") == 1
        out = capsys.readouterr().out
        assert "Unsupported" in out
