# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_picker_print.py
Description: Tests for cmd picker --pick-print and widget output.
Author: Zev
Date: 2026-04-15
"""

import io
import sys
from unittest import mock

import pytest

from pigit.git.cmds._picker import CmdNewPickerLoop, run_cmd_new_picker
from pigit.git.cmds._picker_adapter import CmdNewEntry
from pigit.handlers.cmd_handler import handle_widget


class TestPickerPrintOnly:
    def test_execute_command_print_only_no_args(self, monkeypatch):
        """Print-only outputs pigit cmd <name> when no args."""
        captured = io.StringIO()
        monkeypatch.setattr(sys.stdout, "write", captured.write)
        monkeypatch.setattr(sys.stdout, "flush", lambda: None)

        entry = CmdNewEntry(
            name="b.o", help_text="checkout", category="branch",
            is_dangerous=False, has_args=False,
        )
        loop = CmdNewPickerLoop.__new__(CmdNewPickerLoop)
        loop._print_only = True
        loop._alt = False

        result = loop._execute_command(entry, None)
        assert result == (0, None)
        assert captured.getvalue().strip() == "pigit cmd b.o"

    def test_execute_command_print_only_with_args(self, monkeypatch):
        """Print-only outputs pigit cmd <name> <args> after arg prompt."""
        captured = io.StringIO()
        monkeypatch.setattr(sys.stdout, "write", captured.write)
        monkeypatch.setattr(sys.stdout, "flush", lambda: None)
        monkeypatch.setattr(
            "pigit.git.cmds._picker.read_line_cancellable",
            lambda *, write, flush, prompt: "feature bugfix",
        )

        entry = CmdNewEntry(
            name="b.c", help_text="create branch", category="branch",
            is_dangerous=False, has_args=True,
        )
        loop = CmdNewPickerLoop.__new__(CmdNewPickerLoop)
        loop._print_only = True
        loop._alt = False
        loop._renderer = mock.Mock()

        result = loop._execute_command(entry, None)
        assert result == (0, None)
        output = captured.getvalue()
        assert "pigit cmd b.c feature bugfix" in output

    def test_execute_command_cancellation_returns_none(self, monkeypatch):
        """Esc during arg prompt returns None even in print_only."""
        monkeypatch.setattr(
            "pigit.git.cmds._picker.read_line_cancellable",
            lambda *, write, flush, prompt: None,
        )

        entry = CmdNewEntry(
            name="b.c", help_text="create branch", category="branch",
            is_dangerous=False, has_args=True,
        )
        loop = CmdNewPickerLoop.__new__(CmdNewPickerLoop)
        loop._print_only = True
        loop._alt = False
        loop._renderer = mock.Mock()

        result = loop._execute_command(entry, None)
        assert result is None

    def test_run_picker_print_only_no_tty(self, monkeypatch):
        """No tty returns error message for print_only too."""
        monkeypatch.setattr("pigit.git.cmds._picker._tty_ok", lambda: False)
        exit_code, message = run_cmd_new_picker(print_only=True)
        assert exit_code == 1
        assert "interactive terminal" in message.lower()

    def test_print_only_writes_to_widget_output_file(self, monkeypatch, tmp_path):
        """When PIGIT_WIDGET_OUTPUT is set, write to file instead of stdout."""
        output_file = tmp_path / "widget.out"
        monkeypatch.setenv("PIGIT_WIDGET_OUTPUT", str(output_file))

        entry = CmdNewEntry(
            name="i.a", help_text="add all", category="index",
            is_dangerous=False, has_args=False,
        )
        loop = CmdNewPickerLoop.__new__(CmdNewPickerLoop)
        loop._print_only = True
        loop._alt = False

        result = loop._execute_command(entry, None)
        assert result == (0, None)
        assert output_file.read_text().strip() == "pigit cmd i.a"


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
        assert "_pigit_cmd_widget" in out
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
