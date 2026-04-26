# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_executor.py
Description: Tests for command execution helpers.
Author: Zev
Date: 2026-04-15
"""

from unittest import mock

from pigit.git.cmds._executor import (
    _execute_handler,
    _expand_script_vars,
)
from pigit.git.cmds._models import ScriptConfig


def test_execute_handler_string():
    executor = mock.Mock()
    executor.exec.return_value = (0, "output")
    execute_step = mock.Mock()
    result = _execute_handler("git branch", ["-a"], executor, execute_step)
    assert result == (0, "output")
    executor.exec.assert_called_once_with("git branch -a")


def test_execute_handler_callable():
    executor = mock.Mock()

    def handler(args):
        return f"git checkout -b {args[0]}"

    executor.exec.return_value = (0, "ok")
    execute_step = mock.Mock()
    result = _execute_handler(handler, ["feature"], executor, execute_step)
    assert result == (0, "ok")
    executor.exec.assert_called_once_with("git checkout -b feature")


def test_execute_handler_script():
    """Script handler runs through _execute_script internally."""
    script = ScriptConfig(steps=["!:echo hello"])
    executor = mock.Mock()
    execute_step = mock.Mock()
    result = _execute_handler(script, [], executor, execute_step)
    assert result[0] == 0
    assert "hello" in result[1]


def test_expand_script_vars():
    env = {"FOO": "bar"}
    assert _expand_script_vars("echo $1", ["hello"], env) == "echo hello"
    assert _expand_script_vars("echo $*", ["a", "b"], env) == "echo a b"
    assert _expand_script_vars("echo ${FOO}", [], env) == "echo bar"
    assert _expand_script_vars("echo $1 $2", ["x"], env) == "echo x $2"
