# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_security.py
Description: Tests for cmd_new security module.
Author: Zev
Date: 2026-04-10
"""

import pytest

from pigit.git.cmds import (
    SecureExecutor,
    SecurityPolicy,
    SecurityError,
)


class TestSecurityPolicy:
    def test_default_policy(self):
        policy = SecurityPolicy()
        assert policy.require_confirmation is True
        assert policy.require_double_confirm is False
        assert policy.allowed_in_ci is True
        assert policy.audit_log is False

    def test_custom_policy(self):
        policy = SecurityPolicy(
            require_confirmation=False,
            require_double_confirm=True,
            audit_log=True,
        )
        assert policy.require_confirmation is False
        assert policy.require_double_confirm is True
        assert policy.audit_log is True


class TestSecureExecutor:
    def test_normalize_command_string(self):
        executor = SecureExecutor()
        parts = executor._normalize_command("git status", None)
        assert parts == ["git", "status"]

    def test_normalize_command_with_args(self):
        executor = SecureExecutor()
        parts = executor._normalize_command("git", ["status", "-s"])
        assert parts == ["git", "status", "-s"]

    def test_normalize_command_list(self):
        executor = SecureExecutor()
        parts = executor._normalize_command(["git", "status"], None)
        assert parts == ["git", "status"]

    def test_validate_safe_command(self):
        executor = SecureExecutor()
        assert executor._validate_command(["git", "status"]) is True
        assert executor._validate_command(["git", "commit", "-m", "message"]) is True

    def test_validate_dangerous_patterns(self):
        executor = SecureExecutor()

        # Test various dangerous patterns
        dangerous_commands = [
            ["git", "status", ";", "rm", "-rf", "/"],
            ["echo", "hello", "|", "sh"],
            ["echo", "hello", "|", "bash"],
            ["echo", "`rm", "-rf", "`"],
            ["echo", "$(rm", "-rf)"],
        ]

        for cmd in dangerous_commands:
            assert executor._validate_command(cmd) is False, f"Should reject: {cmd}"

    def test_audit_log(self):
        executor = SecureExecutor()
        policy = SecurityPolicy(audit_log=True)

        # Simulate audit logging
        executor._audit_log.append({"command": ["git", "status"], "policy": policy})

        log = executor.get_audit_log()
        assert len(log) == 1
        assert log[0]["command"] == ["git", "status"]

    def test_confirm_yes(self, monkeypatch):
        executor = SecureExecutor()
        monkeypatch.setattr("builtins.input", lambda _: "y")

        result = executor.confirm("Proceed?")
        assert result is True

    def test_confirm_no(self, monkeypatch):
        executor = SecureExecutor()
        monkeypatch.setattr("builtins.input", lambda _: "n")

        result = executor.confirm("Proceed?")
        assert result is False

    def test_confirm_empty(self, monkeypatch):
        executor = SecureExecutor()
        monkeypatch.setattr("builtins.input", lambda _: "")

        result = executor.confirm("Proceed?")
        assert result is False

    def test_double_confirm_success(self, monkeypatch):
        executor = SecureExecutor()
        inputs = iter(["y", "yes"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        result = executor.confirm("Proceed?", double_confirm=True)
        assert result is True

    def test_double_confirm_fail_second(self, monkeypatch):
        executor = SecureExecutor()
        inputs = iter(["y", "no"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        result = executor.confirm("Proceed?", double_confirm=True)
        assert result is False

    def test_confirm_keyboard_interrupt(self, monkeypatch):
        executor = SecureExecutor()
        monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(KeyboardInterrupt))

        result = executor.confirm("Proceed?")
        assert result is False
