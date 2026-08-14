"""
Module: pigit/git/cmds/working_tree.py
Description: Working tree commands for cmd_new (w.* namespace).
Author: Zev
Date: 2026-04-10
"""

from __future__ import annotations

from ._decorators import command, alias
from ._models import CommandCategory, SecurityLevel


@command(
    short="w",
    category=CommandCategory.WORKING_TREE,
    help="Show working tree status.",
    has_args=True,
    examples=["pigit cmd w", "pigit cmd w -s"],
    related=["w.s", "w.S", "w.d"],
)
def working_tree(args: list[str]) -> str:
    """Show working tree status."""
    base = "git status"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="w.s",
    category=CommandCategory.WORKING_TREE,
    help="Show short status.",
    has_args=True,
    examples=["pigit cmd w.s", "pigit cmd w.s -b"],
    related=["w", "w.S"],
)
def working_tree_short(args: list[str]) -> str:
    """Show short status."""
    base = "git status -s"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="w.S",
    category=CommandCategory.WORKING_TREE,
    help="Show full status with details.",
    has_args=True,
    examples=["pigit cmd w.S"],
    related=["w", "w.s"],
)
def working_tree_full(args: list[str]) -> str:
    """Show full status."""
    base = "git status -v"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="w.d",
    category=CommandCategory.WORKING_TREE,
    help="Show changes in working tree.",
    has_args=True,
    examples=["pigit cmd w.d", "pigit cmd w.d file.txt"],
    related=["w.ds", "i.d"],
)
def working_tree_diff(args: list[str]) -> str:
    """Show working tree diff."""
    base = "git diff"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="w.ds",
    category=CommandCategory.WORKING_TREE,
    help="Show diff stat summary.",
    has_args=True,
    examples=["pigit cmd w.ds", "pigit cmd w.ds --stat"],
    related=["w.d", "w"],
)
def working_tree_diff_stat(args: list[str]) -> str:
    """Show diff stat."""
    base = "git diff --stat"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="w.c",
    category=CommandCategory.WORKING_TREE,
    help="Clean untracked files.",
    has_args=True,
    dangerous=True,
    confirm_msg="Remove untracked files? This cannot be undone.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd w.c -n", "pigit cmd w.c -f"],
    related=["w"],
)
def working_tree_clean(args: list[str]) -> str:
    """Clean untracked files."""
    base = "git clean"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="w.r",
    category=CommandCategory.WORKING_TREE,
    help="Restore working tree files.",
    has_args=True,
    dangerous=True,
    confirm_msg="Restore files? Local changes will be lost.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd w.r file.txt", "pigit cmd w.r --source=HEAD~1"],
    related=["w.R", "w"],
)
def working_tree_restore(args: list[str]) -> str:
    """Restore files."""
    if args:
        return f"git restore {' '.join(args)}"
    return "git restore"


@command(
    short="w.R",
    category=CommandCategory.WORKING_TREE,
    help="Hard reset working tree to HEAD.",
    dangerous=True,
    confirm_msg="Hard reset working tree? ALL uncommitted changes will be lost!",
    security_level=SecurityLevel.DESTRUCTIVE,
    examples=["pigit cmd w.R"],
    related=["w.r", "i.R"],
)
def working_tree_reset_hard(args: list[str]) -> str:
    """Hard reset working tree."""
    return "git reset --hard HEAD"


# Aliases
alias("ws", "w.s")
alias("wS", "w.S")
alias("wd", "w.d")
alias("wds", "w.ds")
alias("wR", "w.R")
