# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_integration.py
Description: Integration tests for cmd_new system.
Author: Zev
Date: 2026-04-10
"""

import pytest

from pigit.git.cmds import (
    GitCommand,
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


class TestGitCommandIntegration:
    def test_full_workflow(self, fresh_registry):
        """Test a complete command execution workflow."""
        # Register commands
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="b",
                    category=CommandCategory.BRANCH,
                    help="List branches",
                ),
                handler="git branch",
            )
        )
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="b.c",
                    category=CommandCategory.BRANCH,
                    help="Create branch",
                ),
                handler=lambda args: (
                    f"git checkout -b {args[0]}" if args else "git checkout -b"
                ),
            )
        )

        # Create processor with mock config
        processor = GitCommand(registry=fresh_registry, config=create_mock_config())

        # Test help
        help_text = processor.get_help()
        assert "List branches" in help_text
        assert "Create branch" in help_text

    def test_dangerous_command_confirmation(self, fresh_registry, monkeypatch):
        """Test dangerous command requires confirmation."""
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="b.d",
                    category=CommandCategory.BRANCH,
                    help="Delete branch",
                    dangerous=True,
                    confirm_msg="Delete branch?",
                    security_level=SecurityLevel.DANGEROUS,
                ),
                handler="git branch -d",
            )
        )

        processor = GitCommand(registry=fresh_registry, config=create_mock_config())

        # Mock confirmation to return False
        monkeypatch.setattr("builtins.input", lambda _: "n")
        # Ensure CI environment is not set, otherwise confirmation is skipped
        monkeypatch.delenv("CI", raising=False)

        exit_code, output = processor.execute("b.d", ["test-branch"])
        assert exit_code == 1
        assert "Cancelled" in output

    def test_alias_resolution(self, fresh_registry):
        """Test alias resolution in execution."""
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="b.c",
                    category=CommandCategory.BRANCH,
                    help="Create branch",
                ),
                handler="git checkout -b",
            )
        )
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
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="b",
                    category=CommandCategory.BRANCH,
                    help="List branches",
                    examples=["b -a"],
                ),
                handler="git branch",
            )
        )
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="b.d",
                    category=CommandCategory.BRANCH,
                    help="Delete branch",
                ),
                handler="git branch -d",
            )
        )

        processor = GitCommand(registry=fresh_registry, config=create_mock_config())

        results = processor.search("delete")
        assert len(results) == 1
        assert results[0].meta.short == "b.d"

        results = processor.search("branch")
        assert len(results) == 2

    def test_list_dangerous(self, fresh_registry):
        """Test listing dangerous commands."""
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="safe",
                    category=CommandCategory.BRANCH,
                    help="Safe command",
                ),
                handler="git status",
            )
        )
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="dangerous",
                    category=CommandCategory.BRANCH,
                    help="Dangerous command",
                    dangerous=True,
                    confirm_msg="Confirm?",
                    security_level=SecurityLevel.DANGEROUS,
                ),
                handler="git reset --hard",
            )
        )

        processor = GitCommand(registry=fresh_registry, config=create_mock_config())
        dangerous = processor.list_dangerous()

        assert len(dangerous) == 1
        assert dangerous[0].meta.short == "dangerous"

    def test_category_filter(self, fresh_registry):
        """Test filtering commands by category."""
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="b",
                    category=CommandCategory.BRANCH,
                    help="Branch command",
                ),
                handler="git branch",
            )
        )
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="c",
                    category=CommandCategory.COMMIT,
                    help="Commit command",
                ),
                handler="git commit",
            )
        )

        processor = GitCommand(registry=fresh_registry, config=create_mock_config())

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


class TestGitCommandPreview:
    def test_preview_string_handler(self, fresh_registry):
        """Preview returns templated string for string handlers."""
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="s",
                    category=CommandCategory.BRANCH,
                    help="status",
                ),
                handler="git status",
            )
        )
        processor = GitCommand(registry=fresh_registry, config=create_mock_config())
        assert processor.preview("s") == (0, "git status")

    def test_preview_with_args(self, fresh_registry):
        """Preview formats command with arguments."""
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="b.c",
                    category=CommandCategory.BRANCH,
                    help="create",
                ),
                handler=lambda args: (
                    f"git checkout -b {args[0]}" if args else "git checkout -b"
                ),
            )
        )
        processor = GitCommand(registry=fresh_registry, config=create_mock_config())
        assert processor.preview("b.c", ["feature"]) == (0, "git checkout -b feature")

    def test_preview_override(self, fresh_registry):
        """Preview respects config overrides."""
        config = create_mock_config()
        config.overrides["s"] = "git status --short"
        processor = GitCommand(registry=fresh_registry, config=config)
        assert processor.preview("s") == (0, "git status --short")

    def test_preview_unknown_command(self, fresh_registry):
        """Preview returns error for unknown commands with suggestions."""
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="status",
                    category=CommandCategory.BRANCH,
                    help="status",
                ),
                handler="git status",
            )
        )
        processor = GitCommand(registry=fresh_registry, config=create_mock_config())
        exit_code, output = processor.preview("st")
        assert exit_code == 1
        assert "Did you mean" in output


class TestDangerConfirmation:
    """Who gets to skip the danger prompt, and who does not.

    The `CI` environment variable used to be the answer, which meant the same
    command ran with different safety depending on where it was invoked —
    CI systems set that variable by themselves.
    """

    def _processor(self, fresh_registry, *, assume_yes: bool, confirm_dangerous=True):
        from unittest.mock import Mock

        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="w.R",
                    category=CommandCategory.WORKING_TREE,
                    help="Restore files",
                    dangerous=True,
                    security_level=SecurityLevel.DESTRUCTIVE,
                    confirm_msg="Restore files? Local changes will be lost.",
                ),
                handler="git restore .",
            )
        )
        config = create_mock_config()
        config.settings["confirm_dangerous"] = confirm_dangerous
        executor = Mock()
        executor.confirm.return_value = False
        executor.exec.return_value = (0, "")
        processor = GitCommand(
            registry=fresh_registry,
            config=config,
            executor=executor,
            assume_yes=assume_yes,
        )
        return processor, executor

    def test_ci_is_not_a_reason_to_skip(self, fresh_registry, monkeypatch):
        """This is the regression: `CI` is set by the environment, not the
        user, and used to switch the safety net off silently."""
        monkeypatch.setenv("CI", "true")
        processor, executor = self._processor(fresh_registry, assume_yes=False)

        exit_code, output = processor.execute("w.R")

        executor.confirm.assert_called_once()
        assert (exit_code, output) == (1, "Cancelled")

    def test_yes_skips_the_prompt(self, fresh_registry, monkeypatch):
        monkeypatch.setenv("CI", "true")
        processor, executor = self._processor(fresh_registry, assume_yes=True)

        exit_code, _output = processor.execute("w.R")

        executor.confirm.assert_not_called()
        assert exit_code == 0

    def test_the_users_own_switch_still_works(self, fresh_registry):
        """`confirm_dangerous = false` is an explicit choice and stays."""
        processor, executor = self._processor(
            fresh_registry, assume_yes=False, confirm_dangerous=False
        )

        exit_code, _output = processor.execute("w.R")

        executor.confirm.assert_not_called()
        assert exit_code == 0

    def test_assume_yes_does_not_touch_ordinary_commands(self, fresh_registry):
        fresh_registry.register(
            CommandDef(
                meta=CommandMeta(
                    short="b",
                    category=CommandCategory.BRANCH,
                    help="List branches",
                ),
                handler="git branch",
            )
        )
        processor, executor = self._processor(fresh_registry, assume_yes=True)

        exit_code, _output = processor.execute("b")

        executor.confirm.assert_not_called()
        assert exit_code == 0


def test_log_contributors_names_the_revision_when_none_is_given():
    """The bare form used to leave the revision off, which makes `git
    shortlog` read the log from stdin whenever stdin is not a terminal — the
    same command summarised the current branch in a terminal and nothing at
    all under a pipe."""
    from pigit.git.cmds.history import log_contributors

    # `@command` replaces the function with a CommandDef; the raw callable
    # is its handler.
    assert log_contributors.handler([]).endswith("HEAD")


def test_log_contributors_leaves_an_explicit_revision_alone():
    """With arguments the revision is the caller's to give — they may be
    passing one, or only options."""
    from pigit.git.cmds.history import log_contributors

    build = log_contributors.handler
    assert build(["v1.0"]) == "git shortlog --summary --numbered v1.0"
    assert build(["-n", "10"]) == "git shortlog --summary --numbered -n 10"
