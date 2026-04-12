# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_integration.py
Description: Integration tests for cmd_new system.
Author: Zev
Date: 2026-04-10
"""

import pytest

from pigit.git.cmds import (
    GitCommandNew,
    CommandRegistry,
    get_registry,
    CommandCategory,
    SecurityLevel,
    CommandMeta,
    CommandDef,
    UserCommandConfig,
)


def create_mock_config():
    """Create mock user config for testing."""
    return UserCommandConfig()


class TestGitCommandNewIntegration:
    def test_full_workflow(self, fresh_registry):
        """Test a complete command execution workflow."""
        # Register commands
        fresh_registry.register(CommandDef(
            meta=CommandMeta(
                short="b",
                category=CommandCategory.BRANCH,
                help="List branches",
            ),
            handler="git branch",
        ))
        fresh_registry.register(CommandDef(
            meta=CommandMeta(
                short="b.c",
                category=CommandCategory.BRANCH,
                help="Create branch",
            ),
            handler=lambda args: f"git checkout -b {args[0]}" if args else "git checkout -b",
        ))

        # Create processor with mock config
        processor = GitCommandNew(registry=fresh_registry, config=create_mock_config())

        # Test help
        help_text = processor.get_help()
        assert "List branches" in help_text
        assert "Create branch" in help_text

    def test_dangerous_command_confirmation(self, fresh_registry, monkeypatch):
        """Test dangerous command requires confirmation."""
        fresh_registry.register(CommandDef(
            meta=CommandMeta(
                short="b.d",
                category=CommandCategory.BRANCH,
                help="Delete branch",
                dangerous=True,
                confirm_msg="Delete branch?",
                security_level=SecurityLevel.DANGEROUS,
            ),
            handler="git branch -d",
        ))

        processor = GitCommandNew(registry=fresh_registry, config=create_mock_config())

        # Mock confirmation to return False
        monkeypatch.setattr("builtins.input", lambda _: "n")
        # Ensure CI environment is not set, otherwise confirmation is skipped
        monkeypatch.delenv("CI", raising=False)

        exit_code, output = processor.execute("b.d", ["test-branch"])
        assert exit_code == 1
        assert "Cancelled" in output

    def test_alias_resolution(self, fresh_registry):
        """Test alias resolution in execution."""
        fresh_registry.register(CommandDef(
            meta=CommandMeta(
                short="b.c",
                category=CommandCategory.BRANCH,
                help="Create branch",
            ),
            handler="git checkout -b",
        ))
        fresh_registry.add_alias("bc", "b.c")

        # Verify alias is resolved
        from pigit.git.cmds import CommandResolver
        resolver = CommandResolver(fresh_registry)
        resolved = resolver.resolve("bc")

        assert resolved.name == "bc"
        assert resolved.resolved == "b.c"
        assert resolved.is_alias is True

    def test_search_commands(self, fresh_registry):
        """Test command search functionality."""
        fresh_registry.register(CommandDef(
            meta=CommandMeta(
                short="b",
                category=CommandCategory.BRANCH,
                help="List branches",
                examples=["b -a"],
            ),
            handler="git branch",
        ))
        fresh_registry.register(CommandDef(
            meta=CommandMeta(
                short="b.d",
                category=CommandCategory.BRANCH,
                help="Delete branch",
            ),
            handler="git branch -d",
        ))

        processor = GitCommandNew(registry=fresh_registry, config=create_mock_config())

        results = processor.search("delete")
        assert len(results) == 1
        assert results[0].meta.short == "b.d"

        results = processor.search("branch")
        assert len(results) == 2

    def test_list_dangerous(self, fresh_registry):
        """Test listing dangerous commands."""
        fresh_registry.register(CommandDef(
            meta=CommandMeta(
                short="safe",
                category=CommandCategory.BRANCH,
                help="Safe command",
            ),
            handler="git status",
        ))
        fresh_registry.register(CommandDef(
            meta=CommandMeta(
                short="dangerous",
                category=CommandCategory.BRANCH,
                help="Dangerous command",
                dangerous=True,
                confirm_msg="Confirm?",
                security_level=SecurityLevel.DANGEROUS,
            ),
            handler="git reset --hard",
        ))

        processor = GitCommandNew(registry=fresh_registry, config=create_mock_config())
        dangerous = processor.list_dangerous()

        assert len(dangerous) == 1
        assert dangerous[0].meta.short == "dangerous"

    def test_category_filter(self, fresh_registry):
        """Test filtering commands by category."""
        fresh_registry.register(CommandDef(
            meta=CommandMeta(
                short="b",
                category=CommandCategory.BRANCH,
                help="Branch command",
            ),
            handler="git branch",
        ))
        fresh_registry.register(CommandDef(
            meta=CommandMeta(
                short="c",
                category=CommandCategory.COMMIT,
                help="Commit command",
            ),
            handler="git commit",
        ))

        processor = GitCommandNew(registry=fresh_registry, config=create_mock_config())

        branch_help = processor.get_help(category=CommandCategory.BRANCH)
        assert "Branch command" in branch_help
        assert "Commit command" not in branch_help

    def test_command_modules_import(self):
        """Test that all command modules can be imported."""
        # This test verifies that all command modules load without errors
        from pigit.git.cmds import (
            branch,
            commit,
            index,
            working_tree,
            push_pull,
            remote,
            history,
            merge,
            conflict,
            submodule,
            settings,
        )

        # Verify modules are loaded
        assert branch is not None
        assert commit is not None
        assert index is not None

        # Verify registry has commands - clear first to ensure fresh state
        registry = get_registry()
        # Note: In real usage, commands are registered at import time
        # We just verify the modules can be imported without errors
