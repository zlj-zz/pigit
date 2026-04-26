# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/merge.py
Description: Merge commands for cmd_new (m.* namespace).
Author: Zev
Date: 2026-04-10
"""

from ._decorators import command, alias
from ._models import CommandCategory, SecurityLevel


@command(
    short="m",
    category=CommandCategory.MERGE,
    help="Merge changes from another branch.",
    has_args=True,
    dangerous=True,
    confirm_msg="Merge branch? This may create merge conflicts.",
    security_level=SecurityLevel.NORMAL,
    examples=["pigit cmd_new m feature-branch", "pigit cmd_new m origin/main"],
    related=["m.a", "m.s", "C"],
)
def merge(args: list[str]) -> str:
    """Merge a branch."""
    base = "git merge"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="m.a",
    category=CommandCategory.MERGE,
    help="Abort current merge.",
    dangerous=True,
    confirm_msg="Abort merge? Uncommitted changes will be lost.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new m.a"],
    related=["m", "m.c"],
)
def merge_abort(args: list[str]) -> str:
    """Abort merge."""
    return "git merge --abort"


@command(
    short="m.c",
    category=CommandCategory.MERGE,
    help="Continue merge after resolving conflicts.",
    examples=["pigit cmd_new m.c"],
    related=["m", "m.a", "C"],
)
def merge_continue(args: list[str]) -> str:
    """Continue merge."""
    return "git merge --continue"


@command(
    short="m.s",
    category=CommandCategory.MERGE,
    help="Show merge status.",
    examples=["pigit cmd_new m.s"],
    related=["m", "w.s"],
)
def merge_status(args: list[str]) -> str:
    """Show merge status."""
    return "git status"


@command(
    short="m.no",
    category=CommandCategory.MERGE,
    help="Merge without fast-forward (create merge commit).",
    has_args=True,
    examples=["pigit cmd_new m.no feature-branch"],
    related=["m", "m.ff"],
)
def merge_no_ff(args: list[str]) -> str:
    """Merge with no fast-forward."""
    base = "git merge --no-ff"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="m.ff",
    category=CommandCategory.MERGE,
    help="Merge with fast-forward only (fail if not possible).",
    has_args=True,
    examples=["pigit cmd_new m.ff feature-branch"],
    related=["m", "m.no"],
)
def merge_ff_only(args: list[str]) -> str:
    """Merge fast-forward only."""
    base = "git merge --ff-only"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="m.squash",
    category=CommandCategory.MERGE,
    help="Squash merge (combine all commits into one).",
    has_args=True,
    examples=["pigit cmd_new m.squash feature-branch"],
    related=["m", "c.F"],
)
def merge_squash(args: list[str]) -> str:
    """Squash merge."""
    base = "git merge --squash"
    if args:
        return f"{base} {' '.join(args)}"
    return base


# Aliases
alias("ma", "m.a")
alias("mc", "m.c")
alias("ms", "m.s")
