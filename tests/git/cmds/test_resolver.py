# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_resolver.py
Description: Tests for cmd_new resolver.
Author: Zev
Date: 2026-04-10
"""

import pytest

from pigit.git.cmds import (
    CommandResolver,
    ResolverError,
    AliasCycleError,
    CommandMeta,
    CommandDef,
    CommandCategory,
)


class TestCommandResolver:
    def test_resolve_exact_match(self, fresh_registry):
        meta = CommandMeta(
            short="b",
            category=CommandCategory.BRANCH,
            help="List branches",
        )
        fresh_registry.register(CommandDef(meta=meta, handler="git branch"))

        resolver = CommandResolver(fresh_registry)
        resolved = resolver.resolve("b")

        assert resolved.name == "b"
        assert resolved.resolved == "b"
        assert resolved.is_alias is False

    def test_resolve_alias(self, fresh_registry):
        meta = CommandMeta(
            short="b.c",
            category=CommandCategory.BRANCH,
            help="Create branch",
        )
        fresh_registry.register(CommandDef(meta=meta, handler="git checkout -b"))
        fresh_registry.add_alias("bc", "b.c")

        resolver = CommandResolver(fresh_registry)
        resolved = resolver.resolve("bc")

        assert resolved.name == "bc"
        assert resolved.resolved == "b.c"
        assert resolved.is_alias is True
        assert "bc" in resolved.alias_chain

    def test_resolve_chain_alias(self, fresh_registry):
        meta = CommandMeta(
            short="branch.create",
            category=CommandCategory.BRANCH,
            help="Create branch",
        )
        fresh_registry.register(CommandDef(meta=meta, handler="git checkout -b"))
        fresh_registry.add_alias("bc", "branch.create")
        fresh_registry.add_alias("newbranch", "bc")

        resolver = CommandResolver(fresh_registry)
        resolved = resolver.resolve("newbranch")

        assert resolved.name == "newbranch"
        assert resolved.resolved == "branch.create"
        assert resolved.is_alias is True
        assert resolved.alias_chain == ["newbranch", "bc"]

    def test_resolve_unknown_command(self, fresh_registry):
        resolver = CommandResolver(fresh_registry)

        with pytest.raises(ResolverError) as exc_info:
            resolver.resolve("unknown")
        assert "Unknown command" in str(exc_info.value)

    def test_resolve_alias_cycle(self, fresh_registry):
        fresh_registry.add_alias("a", "b")
        fresh_registry.add_alias("b", "a")

        resolver = CommandResolver(fresh_registry)

        with pytest.raises(AliasCycleError) as exc_info:
            resolver.resolve("a")
        assert "cycle" in str(exc_info.value).lower()

    def test_resolve_max_depth(self, fresh_registry):
        # Create a long alias chain
        for i in range(15):
            fresh_registry.add_alias(f"a{i}", f"a{i+1}")

        resolver = CommandResolver(fresh_registry)

        with pytest.raises(ResolverError) as exc_info:
            resolver.resolve("a0")
        assert "depth" in str(exc_info.value).lower()

    def test_suggest_similar(self, fresh_registry):
        meta1 = CommandMeta(
            short="branch",
            category=CommandCategory.BRANCH,
            help="Branch command",
        )
        meta2 = CommandMeta(
            short="branches",
            category=CommandCategory.BRANCH,
            help="Branches command",
        )
        fresh_registry.register(CommandDef(meta=meta1, handler="git branch"))
        fresh_registry.register(CommandDef(meta=meta2, handler="git branches"))

        resolver = CommandResolver(fresh_registry)
        suggestions = resolver.suggest("bran")

        assert "branch" in suggestions
        assert "branches" in suggestions

    def test_suggest_limit(self, fresh_registry):
        for i in range(10):
            meta = CommandMeta(
                short=f"cmd{i}",
                category=CommandCategory.BRANCH,
                help=f"Command {i}",
            )
            fresh_registry.register(CommandDef(meta=meta, handler=f"git {i}"))

        resolver = CommandResolver(fresh_registry)
        suggestions = resolver.suggest("cmd", max_suggestions=5)

        assert len(suggestions) <= 5
