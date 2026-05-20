"""
Module: tests/test_init.py
Description: Tests for shell integration init module.
Author: Zev
Date: 2026-05-20
"""

from __future__ import annotations

import os
from unittest import mock

import pytest

from pigit.init import (
    get_shell,
    _resolve_shell,
    _first_arg_completion,
    run_shell_init,
)


class TestGetShell:
    def test_reads_shell_env(self):
        with mock.patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
            assert get_shell() == "zsh"

    def test_reads_bash_env(self):
        with mock.patch.dict(os.environ, {"SHELL": "/usr/local/bin/bash"}):
            assert get_shell() == "bash"

    def test_empty_when_missing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            assert get_shell() == ""


class TestResolveShell:
    def test_bash_passthrough(self):
        assert _resolve_shell("bash") == "bash"

    def test_zsh_passthrough(self):
        assert _resolve_shell("zsh") == "zsh"

    def test_fish_passthrough(self):
        assert _resolve_shell("fish") == "fish"

    def test_nil_falls_back_to_env(self):
        with mock.patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
            assert _resolve_shell("nil") == "zsh"

    def test_empty_falls_back_to_env(self):
        with mock.patch.dict(os.environ, {"SHELL": "/bin/bash"}):
            assert _resolve_shell("") == "bash"

    def test_unsupported_returns_empty(self):
        with mock.patch.dict(os.environ, {"SHELL": "/bin/unsupported"}):
            assert _resolve_shell("unsupported") == ""

    def test_case_insensitive(self):
        assert _resolve_shell("BASH") == "bash"
        assert _resolve_shell("Zsh") == "zsh"


class TestFirstArgCompletion:
    class _Meta:
        arg_completion = None

    class _MetaList:
        arg_completion = []

    class _MetaListValue:
        arg_completion = [mock.Mock(value="path")]

    class _MetaStr:
        arg_completion = mock.Mock(value="branch")

    def test_none_returns_empty(self):
        assert _first_arg_completion(self._Meta()) == ""

    def test_empty_list_returns_empty(self):
        assert _first_arg_completion(self._MetaList()) == ""

    def test_list_with_value_returns_first(self):
        assert _first_arg_completion(self._MetaListValue()) == "path"

    def test_non_list_returns_value(self):
        assert _first_arg_completion(self._MetaStr()) == "branch"


class TestRunShellInit:
    def _make_parser(self):
        class FakeMeta:
            short = "st"
            help = "status"
            arg_completion = None

        class FakeCmdDef:
            meta = FakeMeta()

        class FakeRegistry:
            def get_all(self):
                return [FakeCmdDef()]

            def get_aliases(self):
                return {"bl": "branch -l"}

        class FakeParser:
            def to_dict(self):
                return {
                    "prog": "pigit",
                    "args": {
                        "cmd": {
                            "args": {},
                        },
                    },
                }

        return FakeParser(), FakeRegistry()

    def test_empty_shell_returns_nothing(self, capsys):
        parser, registry = self._make_parser()
        with mock.patch("pigit.init.get_shell", return_value=""):
            with mock.patch("pigit.git.cmds.register_user_commands", return_value=None):
                with mock.patch("pigit.git.cmds.get_registry", return_value=registry):
                    run_shell_init("", parser)
        captured = capsys.readouterr()
        assert captured.out == "\n"

    def test_unsupported_shell_returns_nothing(self, capsys):
        parser, registry = self._make_parser()
        with mock.patch("pigit.init.get_shell", return_value=""):
            with mock.patch("pigit.git.cmds.register_user_commands", return_value=None):
                with mock.patch("pigit.git.cmds.get_registry", return_value=registry):
                    run_shell_init("powershell", parser)
        captured = capsys.readouterr()
        assert captured.out == "\n"

    def test_bash_includes_completion_and_function(self, capsys):
        parser, registry = self._make_parser()
        with mock.patch("pigit.git.cmds.register_user_commands", return_value=None):
            with mock.patch("pigit.git.cmds.get_registry", return_value=registry):
                run_shell_init("bash", parser)
        captured = capsys.readouterr()
        assert "complete" in captured.out
        assert "pigit() {" in captured.out
        assert "repo cd" in captured.out

    def test_zsh_includes_completion_and_function(self, capsys):
        parser, registry = self._make_parser()
        with mock.patch("pigit.git.cmds.register_user_commands", return_value=None):
            with mock.patch("pigit.git.cmds.get_registry", return_value=registry):
                run_shell_init("zsh", parser)
        captured = capsys.readouterr()
        assert "compdef" in captured.out
        assert "pigit() {" in captured.out

    def test_fish_includes_completion_and_function(self, capsys):
        parser, registry = self._make_parser()
        with mock.patch("pigit.git.cmds.register_user_commands", return_value=None):
            with mock.patch("pigit.git.cmds.get_registry", return_value=registry):
                run_shell_init("fish", parser)
        captured = capsys.readouterr()
        assert "complete" in captured.out
        assert "function pigit" in captured.out

    def test_auto_detect_from_env(self, capsys):
        parser, registry = self._make_parser()
        with mock.patch("pigit.init.get_shell", return_value="bash"):
            with mock.patch("pigit.git.cmds.register_user_commands", return_value=None):
                with mock.patch("pigit.git.cmds.get_registry", return_value=registry):
                    run_shell_init("nil", parser)
        captured = capsys.readouterr()
        assert "pigit() {" in captured.out

    def test_includes_user_commands_and_aliases(self, capsys):
        parser, registry = self._make_parser()
        with mock.patch("pigit.git.cmds.register_user_commands", return_value=None):
            with mock.patch("pigit.git.cmds.get_registry", return_value=registry):
                run_shell_init("bash", parser)
        captured = capsys.readouterr()
        assert "st" in captured.out
        assert "bl" in captured.out
