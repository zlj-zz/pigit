# -*- coding: utf-8 -*-
"""Tests for built-in ``pigit cmd --pick`` TUI helper."""

from unittest.mock import patch

from pigit.git.cmd_picker import run_command_picker
from pigit.git.cmd_proxy import GitProxy


def test_run_command_picker_no_tty():
    g = GitProxy(extra_cmds={})
    with patch("pigit.git.cmd_picker._tty_ok", return_value=False):
        code, msg = run_command_picker(g)
    assert code == 1
    assert msg and "interactive" in msg.lower()
