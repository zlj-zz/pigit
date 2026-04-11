# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_models.py
Description: Tests for cmd_new data models.
Author: Project Team
Date: 2026-04-10
"""

import pytest

from pigit.git.cmds import (
    CommandCategory,
    SecurityLevel,
    CommandSource,
    CommandMeta,
    CommandDef,
    ResolvedCommand,
    CompletionItem,
    ValidationResult,
)


class TestCommandCategory:
    def test_category_values(self):
        assert CommandCategory.BRANCH.value == "branch"
        assert CommandCategory.COMMIT.value == "commit"
        assert CommandCategory.INDEX.value == "index"

    def test_all_categories(self):
        categories = list(CommandCategory)
        assert len(categories) == 16  # Including ALIAS and SCRIPT


class TestSecurityLevel:
    def test_security_levels(self):
        assert SecurityLevel.SAFE
        assert SecurityLevel.NORMAL
        assert SecurityLevel.DANGEROUS
        assert SecurityLevel.DESTRUCTIVE


class TestCommandSource:
    def test_source_values(self):
        assert CommandSource.BUILTIN.value == "builtin"
        assert CommandSource.ALIAS.value == "alias"
        assert CommandSource.SCRIPT.value == "script"
        assert CommandSource.OVERRIDE.value == "override"


class TestCommandMeta:
    def test_basic_creation(self):
        meta = CommandMeta(
            short="b.c",
            category=CommandCategory.BRANCH,
            help="Create branch",
        )
        assert meta.short == "b.c"
        assert meta.category == CommandCategory.BRANCH
        assert meta.help == "Create branch"
        assert meta.has_args is False
        assert meta.dangerous is False

    def test_with_all_fields(self):
        meta = CommandMeta(
            short="b.d",
            category=CommandCategory.BRANCH,
            help="Delete branch",
            has_args=True,
            dangerous=True,
            confirm_msg="Delete?",
            examples=["b.d old-branch"],
            related=["b.D"],
            security_level=SecurityLevel.DANGEROUS,
            source=CommandSource.BUILTIN,
            is_user_defined=False,
        )
        assert meta.dangerous is True
        assert meta.confirm_msg == "Delete?"
        assert meta.examples == ["b.d old-branch"]
        assert meta.security_level == SecurityLevel.DANGEROUS
        assert meta.source == CommandSource.BUILTIN
        assert meta.is_user_defined is False

    def test_defaults(self):
        meta = CommandMeta(
            short="b",
            category=CommandCategory.BRANCH,
            help="List branches",
        )
        assert meta.examples == []
        assert meta.related == []
        assert meta.security_level == SecurityLevel.SAFE
        assert meta.source == CommandSource.BUILTIN
        assert meta.is_user_defined is False


class TestCommandDef:
    def test_with_string_handler(self):
        meta = CommandMeta(
            short="b",
            category=CommandCategory.BRANCH,
            help="List branches",
        )
        cmd_def = CommandDef(meta=meta, handler="git branch")
        assert cmd_def.meta == meta
        assert cmd_def.handler == "git branch"

    def test_with_callable_handler(self):
        def handler(args):
            return "git branch"

        meta = CommandMeta(
            short="b",
            category=CommandCategory.BRANCH,
            help="List branches",
        )
        cmd_def = CommandDef(meta=meta, handler=handler)
        assert callable(cmd_def.handler)


class TestResolvedCommand:
    def test_creation(self):
        meta = CommandMeta(
            short="b.c",
            category=CommandCategory.BRANCH,
            help="Create branch",
        )
        cmd_def = CommandDef(meta=meta, handler="git checkout -b")

        resolved = ResolvedCommand(
            name="bc",
            resolved="b.c",
            definition=cmd_def,
            is_alias=True,
            alias_chain=["bc"],
        )
        assert resolved.name == "bc"
        assert resolved.resolved == "b.c"
        assert resolved.is_alias is True
        assert resolved.alias_chain == ["bc"]


class TestCompletionItem:
    def test_creation(self):
        item = CompletionItem(
            value="b.c",
            display="b.c",
            description="Create branch",
            priority=10,
        )
        assert item.value == "b.c"
        assert item.priority == 10

    def test_default_priority(self):
        item = CompletionItem(
            value="b",
            display="b",
            description="List branches",
        )
        assert item.priority == 0


class TestValidationResult:
    def test_valid(self):
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.errors == []
        assert bool(result) is True

    def test_invalid(self):
        result = ValidationResult(is_valid=False, errors=["Error 1", "Error 2"])
        assert result.is_valid is False
        assert result.errors == ["Error 1", "Error 2"]
        assert bool(result) is False

    def test_invalid_no_errors(self):
        result = ValidationResult(is_valid=False)
        assert result.is_valid is False
        assert result.errors == []
