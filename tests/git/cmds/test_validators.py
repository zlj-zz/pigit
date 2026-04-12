# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_validators.py
Description: Tests for cmd_new validators.
Author: Zev
Date: 2026-04-10
"""

import pytest

from pigit.git.cmds import (
    CommandNameValidator,
    DangerousCommandValidator,
    CompositeValidator,
    CommandMeta,
    CommandDef,
    CommandCategory,
    SecurityLevel,
)


class TestCommandNameValidator:
    def test_valid_simple_name(self):
        validator = CommandNameValidator()
        meta = CommandMeta(
            short="b",
            category=CommandCategory.BRANCH,
            help="List branches",
        )
        cmd_def = CommandDef(meta=meta, handler="git branch")
        result = validator.validate(cmd_def)
        assert result.is_valid is True

    def test_valid_hierarchical_name(self):
        validator = CommandNameValidator()
        meta = CommandMeta(
            short="b.c",
            category=CommandCategory.BRANCH,
            help="Create branch",
        )
        cmd_def = CommandDef(meta=meta, handler="git checkout -b")
        result = validator.validate(cmd_def)
        assert result.is_valid is True

    def test_invalid_empty_name(self):
        validator = CommandNameValidator()
        meta = CommandMeta(
            short="",
            category=CommandCategory.BRANCH,
            help="Empty command",
        )
        cmd_def = CommandDef(meta=meta, handler="git branch")
        result = validator.validate(cmd_def)
        assert result.is_valid is False
        assert "cannot be empty" in result.errors[0]

    def test_valid_name_with_uppercase(self):
        # Uppercase letters are now allowed in command names
        validator = CommandNameValidator()
        meta = CommandMeta(
            short="b.D",
            category=CommandCategory.BRANCH,
            help="Force delete branch",
        )
        cmd_def = CommandDef(meta=meta, handler="git branch -D")
        result = validator.validate(cmd_def)
        assert result.is_valid is True

    def test_invalid_name_starting_with_dot(self):
        validator = CommandNameValidator()
        meta = CommandMeta(
            short=".invalid",
            category=CommandCategory.BRANCH,
            help="Invalid command",
        )
        cmd_def = CommandDef(meta=meta, handler="git branch")
        result = validator.validate(cmd_def)
        assert result.is_valid is False

    def test_invalid_reserved_name(self):
        validator = CommandNameValidator()
        meta = CommandMeta(
            short="help",
            category=CommandCategory.BRANCH,
            help="Invalid command",
        )
        cmd_def = CommandDef(meta=meta, handler="git help")
        result = validator.validate(cmd_def)
        assert result.is_valid is False
        assert "reserved" in result.errors[0]

    def test_name_too_long(self):
        validator = CommandNameValidator()
        meta = CommandMeta(
            short="a" * 50,
            category=CommandCategory.BRANCH,
            help="Too long",
        )
        cmd_def = CommandDef(meta=meta, handler="git branch")
        result = validator.validate(cmd_def)
        assert result.is_valid is False
        assert "too long" in result.errors[0]


class TestDangerousCommandValidator:
    def test_non_dangerous_valid(self):
        validator = DangerousCommandValidator()
        meta = CommandMeta(
            short="b",
            category=CommandCategory.BRANCH,
            help="List branches",
            dangerous=False,
        )
        cmd_def = CommandDef(meta=meta, handler="git branch")
        result = validator.validate(cmd_def)
        assert result.is_valid is True

    def test_dangerous_missing_confirm_msg(self):
        validator = DangerousCommandValidator()
        meta = CommandMeta(
            short="b.d",
            category=CommandCategory.BRANCH,
            help="Delete branch",
            dangerous=True,
            security_level=SecurityLevel.DANGEROUS,
        )
        cmd_def = CommandDef(meta=meta, handler="git branch -d")
        result = validator.validate(cmd_def)
        assert result.is_valid is False
        assert "confirm_msg" in result.errors[0]

    def test_dangerous_wrong_security_level(self):
        validator = DangerousCommandValidator()
        meta = CommandMeta(
            short="b.d",
            category=CommandCategory.BRANCH,
            help="Delete branch",
            dangerous=True,
            confirm_msg="Delete?",
            security_level=SecurityLevel.SAFE,
        )
        cmd_def = CommandDef(meta=meta, handler="git branch -d")
        result = validator.validate(cmd_def)
        assert result.is_valid is False
        assert "security_level" in result.errors[0]

    def test_dangerous_valid(self):
        validator = DangerousCommandValidator()
        meta = CommandMeta(
            short="b.d",
            category=CommandCategory.BRANCH,
            help="Delete branch",
            dangerous=True,
            confirm_msg="Delete?",
            security_level=SecurityLevel.DANGEROUS,
        )
        cmd_def = CommandDef(meta=meta, handler="git branch -d")
        result = validator.validate(cmd_def)
        assert result.is_valid is True


class TestCompositeValidator:
    def test_valid_command(self):
        validator = CompositeValidator()
        meta = CommandMeta(
            short="b",
            category=CommandCategory.BRANCH,
            help="List branches",
        )
        cmd_def = CommandDef(meta=meta, handler="git branch")
        result = validator.validate(cmd_def)
        assert result.is_valid is True

    def test_multiple_errors(self):
        validator = CompositeValidator()
        meta = CommandMeta(
            short="help",
            category=CommandCategory.BRANCH,
            help="Reserved name",
            dangerous=True,
        )
        cmd_def = CommandDef(meta=meta, handler="git help")
        result = validator.validate(cmd_def)
        assert result.is_valid is False
        assert len(result.errors) >= 1
