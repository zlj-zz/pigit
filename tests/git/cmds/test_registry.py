# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_registry.py
Description: Tests for cmd_new registry.
Author: Zev
Date: 2026-04-10
"""

import pytest
import threading
import time

from pigit.git.cmds import (
    CommandRegistry,
    RegistryError,
    CommandMeta,
    CommandDef,
    CommandCategory,
)


class TestCommandRegistry:
    def test_singleton(self):
        reg1 = CommandRegistry()
        reg2 = CommandRegistry()
        assert reg1 is reg2

    def test_register_command(self, fresh_registry):
        meta = CommandMeta(
            short="test.cmd",
            category=CommandCategory.BRANCH,
            help="Test command",
        )
        cmd_def = CommandDef(meta=meta, handler="git test")

        result = fresh_registry.register(cmd_def)
        assert result.is_valid is True
        assert fresh_registry.is_registered("test.cmd")

    def test_register_duplicate(self, fresh_registry):
        meta = CommandMeta(
            short="test.cmd",
            category=CommandCategory.BRANCH,
            help="Test command",
        )
        cmd_def = CommandDef(meta=meta, handler="git test")

        fresh_registry.register(cmd_def)

        with pytest.raises(RegistryError):
            fresh_registry.register(cmd_def)

    def test_get_command(self, fresh_registry):
        meta = CommandMeta(
            short="test.cmd",
            category=CommandCategory.BRANCH,
            help="Test command",
        )
        cmd_def = CommandDef(meta=meta, handler="git test")
        fresh_registry.register(cmd_def)

        retrieved = fresh_registry.get("test.cmd")
        assert retrieved is not None
        assert retrieved.meta.short == "test.cmd"

    def test_get_nonexistent(self, fresh_registry):
        retrieved = fresh_registry.get("nonexistent")
        assert retrieved is None

    def test_add_alias(self, fresh_registry):
        meta = CommandMeta(
            short="test.cmd",
            category=CommandCategory.BRANCH,
            help="Test command",
        )
        cmd_def = CommandDef(meta=meta, handler="git test")
        fresh_registry.register(cmd_def)

        fresh_registry.add_alias("tc", "test.cmd")
        assert fresh_registry.is_alias("tc")
        assert fresh_registry.get_aliases()["tc"] == "test.cmd"

    def test_add_alias_conflicts_with_command(self, fresh_registry):
        meta = CommandMeta(
            short="test.cmd",
            category=CommandCategory.BRANCH,
            help="Test command",
        )
        cmd_def = CommandDef(meta=meta, handler="git test")
        fresh_registry.register(cmd_def)

        with pytest.raises(RegistryError):
            fresh_registry.add_alias("test.cmd", "other")

    def test_get_all(self, fresh_registry):
        meta1 = CommandMeta(
            short="test.cmd1",
            category=CommandCategory.BRANCH,
            help="Test command 1",
        )
        meta2 = CommandMeta(
            short="test.cmd2",
            category=CommandCategory.COMMIT,
            help="Test command 2",
        )
        fresh_registry.register(CommandDef(meta=meta1, handler="git test1"))
        fresh_registry.register(CommandDef(meta=meta2, handler="git test2"))

        all_cmds = fresh_registry.get_all()
        assert len(all_cmds) == 2

    def test_get_by_category(self, fresh_registry):
        meta1 = CommandMeta(
            short="test.cmd1",
            category=CommandCategory.BRANCH,
            help="Test command 1",
        )
        meta2 = CommandMeta(
            short="test.cmd2",
            category=CommandCategory.COMMIT,
            help="Test command 2",
        )
        fresh_registry.register(CommandDef(meta=meta1, handler="git test1"))
        fresh_registry.register(CommandDef(meta=meta2, handler="git test2"))

        branch_cmds = fresh_registry.get_all(CommandCategory.BRANCH)
        assert len(branch_cmds) == 1
        assert branch_cmds[0].meta.short == "test.cmd1"

    def test_get_dangerous(self, fresh_registry):
        from pigit.git.cmds import SecurityLevel

        meta_safe = CommandMeta(
            short="safe.cmd",
            category=CommandCategory.BRANCH,
            help="Safe command",
            dangerous=False,
        )
        meta_dangerous = CommandMeta(
            short="dangerous.cmd",
            category=CommandCategory.BRANCH,
            help="Dangerous command",
            dangerous=True,
            confirm_msg="Confirm?",
            security_level=SecurityLevel.DANGEROUS,
        )
        fresh_registry.register(CommandDef(meta=meta_safe, handler="git safe"))
        fresh_registry.register(
            CommandDef(meta=meta_dangerous, handler="git dangerous")
        )

        dangerous = fresh_registry.get_dangerous()
        assert len(dangerous) == 1
        assert dangerous[0].meta.short == "dangerous.cmd"

    def test_thread_safety(self, fresh_registry):
        errors = []

        def register_commands(prefix):
            try:
                for i in range(10):
                    meta = CommandMeta(
                        short=f"{prefix}.cmd{i}",
                        category=CommandCategory.BRANCH,
                        help=f"Command {i}",
                    )
                    fresh_registry.register(CommandDef(meta=meta, handler=f"git {i}"))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_commands, args=(f"thread{i}",))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(fresh_registry.get_all()) == 50

    def test_clear(self, fresh_registry):
        meta = CommandMeta(
            short="test.cmd",
            category=CommandCategory.BRANCH,
            help="Test command",
        )
        fresh_registry.register(CommandDef(meta=meta, handler="git test"))
        fresh_registry.add_alias("tc", "test.cmd")

        fresh_registry.clear()
        assert len(fresh_registry.get_all()) == 0
        assert len(fresh_registry.get_aliases()) == 0
