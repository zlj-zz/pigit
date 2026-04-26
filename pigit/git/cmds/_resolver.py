# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_resolver.py
Description: Command resolver with hierarchical naming and alias resolution.
Author: Zev
Date: 2026-04-10
"""

from dataclasses import dataclass
from typing import Optional

from ._models import ResolvedCommand, CommandDef
from ._registry import CommandRegistry, get_registry


class ResolverError(Exception):
    """Command resolution error."""

    pass


class AliasCycleError(ResolverError):
    """Alias cycle detected error."""

    pass


@dataclass
class ResolutionContext:
    """Context for command resolution.

    Attributes:
        alias_chain: Chain of alias resolutions
        depth: Current resolution depth
        max_depth: Maximum allowed depth
    """

    alias_chain: list[str]
    depth: int
    max_depth: int = 10


class CommandResolver:
    """Command resolver handling hierarchical naming and alias expansion.

    Supports:
    - Exact match
    - Alias expansion
    - Hierarchical naming resolution (b.c -> branch_create)
    - Fuzzy matching suggestions
    """

    # Mapping of common prefixes to full words (class constant)
    _PREFIX_MAP = {
        "b": "branch",
        "c": "commit",
        "i": "index",
        "w": "working_tree",
        "r": "remote",
        "p": "push",
        "f": "fetch",
        "l": "log",
        "s": "stash",
        "t": "tag",
        "m": "merge",
        "C": "conflict",
        "S": "submodule",
        "set": "settings",
    }

    # Mapping of common actions to full words (class constant)
    _ACTION_MAP = {
        "c": "create",
        "d": "delete",
        "D": "force_delete",
        "m": "move",
        "v": "verbose",
        "a": "all",
        "o": "checkout",
        "O": "checkout_interactive",
        "f": "fixup",
        "F": "amend",
        "r": "reset",
        "R": "hard_reset",
        "s": "status",
        "S": "status_full",
    }

    def __init__(self, registry: Optional[CommandRegistry] = None):
        self._registry = registry or get_registry()

    def resolve(self, input_name: str) -> ResolvedCommand:
        """Resolve input command name to command definition.

        Args:
            input_name: Input command name (may include aliases)

        Returns:
            ResolvedCommand with resolution details

        Raises:
            ResolverError: If command cannot be resolved
            AliasCycleError: If alias cycle detected
        """
        context = ResolutionContext(
            alias_chain=[],
            depth=0,
        )

        resolved_name, definition = self._resolve_recursive(input_name, context)

        return ResolvedCommand(
            name=input_name,
            resolved=resolved_name,
            definition=definition,
            is_alias=len(context.alias_chain) > 0,
            alias_chain=context.alias_chain,
        )

    def _resolve_recursive(
        self, name: str, context: ResolutionContext
    ) -> tuple[str, CommandDef]:
        """Recursively resolve command name.

        Args:
            name: Current name to resolve
            context: Resolution context

        Returns:
            Tuple of (resolved_name, command_definition)

        Raises:
            AliasCycleError: If cycle detected
            ResolverError: If max depth exceeded or not found
        """
        context.depth += 1
        if context.depth > context.max_depth:
            raise ResolverError(f"Resolution depth exceeded for '{name}'")

        # Check for alias
        if self._registry.is_alias(name):
            target = self._registry.get_aliases().get(name)
            if target in context.alias_chain:
                raise AliasCycleError(
                    f"Alias cycle detected: {' -> '.join(context.alias_chain)} -> {target}"
                )
            context.alias_chain.append(name)
            return self._resolve_recursive(target, context)

        # Check for exact match
        cmd_def = self._registry.get(name)
        if cmd_def:
            return name, cmd_def

        # Try hierarchical resolution (e.g., b.c -> branch_create)
        hierarchical = self._try_hierarchical(name)
        if hierarchical:
            return hierarchical

        raise ResolverError(f"Unknown command: '{name}'")

    def _try_hierarchical(self, name: str) -> Optional[tuple[str, CommandDef]]:
        """Try hierarchical naming resolution.

        Examples:
            b.c -> branch_create
            b.d -> branch_delete

        Args:
            name: Hierarchical name like "b.c"

        Returns:
            Tuple of (resolved_name, definition) or None
        """
        if "." not in name:
            return None

        parts = name.split(".")
        if len(parts) != 2:
            return None

        prefix, action = parts

        # Build possible command names
        candidates = self._build_candidates(prefix, action)

        for candidate in candidates:
            cmd_def = self._registry.get(candidate)
            if cmd_def:
                return candidate, cmd_def

        return None

    def _build_candidates(self, prefix: str, action: str) -> list[str]:
        """Build candidate command names from prefix and action.

        Args:
            prefix: Command prefix (e.g., 'b' for branch)
            action: Action suffix (e.g., 'c' for create)

        Returns:
            List of candidate names to try
        """
        candidates = []

        # Direct match: b.c
        candidates.append(f"{prefix}_{action}")

        # Expanded match: branch_create
        if prefix in self._PREFIX_MAP and action in self._ACTION_MAP:
            candidates.append(f"{self._PREFIX_MAP[prefix]}_{self._ACTION_MAP[action]}")

        return candidates

    def suggest(self, input_name: str, max_suggestions: int = 5) -> list[str]:
        """Suggest similar commands for unknown input.

        Args:
            input_name: Input command name
            max_suggestions: Maximum suggestions to return

        Returns:
            List of suggested command names
        """
        suggestions = []
        input_lower = input_name.lower()

        # Use generators to avoid building full lists
        for cmd_def in self._registry.get_all():
            name = cmd_def.meta.short
            if name.startswith(input_name) or input_name in name:
                suggestions.append(name)
                if len(suggestions) >= max_suggestions:
                    return suggestions

        for alias in self._registry.get_aliases().keys():
            if alias.startswith(input_name) or input_name in alias:
                suggestions.append(alias)
                if len(suggestions) >= max_suggestions:
                    return suggestions

        return suggestions
