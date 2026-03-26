# -*- coding: utf-8 -*-
"""Tests for built-in ``pigit cmd --pick`` TUI helper."""

from unittest.mock import patch

from pigit.git.cmd_picker import run_command_picker
from pigit.git.cmd_proxy import GitProxy


def test_run_command_picker_quit():
    g = GitProxy(extra_cmds={})
    with patch("pigit.git.cmd_picker._tty_ok", return_value=True):
        code, msg = run_command_picker(
            g,
            read_char=lambda: "q",
            write=lambda s: None,
            flush=lambda: None,
            read_line=lambda p: "",
        )
    assert (code, msg) == (0, None)


def test_run_command_picker_no_tty():
    g = GitProxy(extra_cmds={})
    with patch("pigit.git.cmd_picker._tty_ok", return_value=False):
        code, msg = run_command_picker(g)
    assert code == 1
    assert msg and "interactive" in msg.lower()


def test_run_command_picker_ctrl_c():
    g = GitProxy(extra_cmds={})

    def boom():
        raise KeyboardInterrupt

    with patch("pigit.git.cmd_picker._tty_ok", return_value=True):
        code, msg = run_command_picker(g, read_char=boom, write=lambda s: None, flush=lambda: None)
    assert code == 130
    assert msg is None


def test_run_command_picker_terminal_too_small(monkeypatch):
    g = GitProxy(extra_cmds={})

    def tiny():
        # Header (3) + bottom status + input (2) + list (>=1) => need >=6 rows.
        return (80, 5)

    monkeypatch.setattr("pigit.termui.scenes.list_picker.terminal_size", tiny)
    with patch("pigit.git.cmd_picker._tty_ok", return_value=True):
        code, msg = run_command_picker(
            g, read_char=lambda: "q", write=lambda s: None, flush=lambda: None
        )
    assert code == 1
    assert msg and "too small" in msg.lower()
