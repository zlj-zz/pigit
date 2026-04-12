# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/branch.py
Description: Branch commands for cmd_new (b.* namespace).
Author: Zev
Date: 2026-04-10
"""

from ._decorators import command, alias
from ._models import CommandCategory, SecurityLevel


@command(
    short="b",
    category=CommandCategory.BRANCH,
    help="List, create, rename, and delete branches.",
    has_args=True,
    examples=["pigit cmd_new b", "pigit cmd_new b --list"],
    related=["b.c", "b.d", "b.m"],
)
def branch_list(args: list[str]) -> str:
    """List branches."""
    return "git branch"


@command(
    short="b.c",
    category=CommandCategory.BRANCH,
    help="Create a new branch.",
    has_args=True,
    examples=["pigit cmd_new b.c feature-branch", "pigit cmd_new b.c hotfix/123 main"],
    related=["b", "b.o"],
)
def branch_create(args: list[str]) -> str:
    """Create a new branch."""
    if not args:
        return "git checkout -b"
    return f"git checkout -b {' '.join(args)}"


@command(
    short="b.d",
    category=CommandCategory.BRANCH,
    help="Delete a local branch.",
    has_args=True,
    dangerous=True,
    confirm_msg="Delete branch? Unmerged changes may be lost.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new b.d old-feature"],
    related=["b.D", "b"],
)
def branch_delete(args: list[str]) -> str:
    """Delete a branch."""
    if not args:
        return "git branch -d"
    return f"git branch -d {' '.join(args)}"


@command(
    short="b.D",
    category=CommandCategory.BRANCH,
    help="Force delete a branch (even if unmerged).",
    has_args=True,
    dangerous=True,
    confirm_msg="Force delete branch? Unmerged changes WILL be lost!",
    security_level=SecurityLevel.DESTRUCTIVE,
    examples=["pigit cmd_new b.D stale-branch"],
    related=["b.d", "b"],
)
def branch_force_delete(args: list[str]) -> str:
    """Force delete a branch."""
    if not args:
        return "git branch -D"
    return f"git branch -D {' '.join(args)}"


@command(
    short="b.m",
    category=CommandCategory.BRANCH,
    help="Rename (move) a branch.",
    has_args=True,
    examples=["pigit cmd_new b.m old-name new-name"],
    related=["b.M", "b"],
)
def branch_move(args: list[str]) -> str:
    """Rename a branch."""
    if len(args) >= 2:
        return f"git branch --move {' '.join(args[:2])}"
    return "git branch --move"


@command(
    short="b.M",
    category=CommandCategory.BRANCH,
    help="Force rename a branch (overwrite if exists).",
    has_args=True,
    dangerous=True,
    confirm_msg="Force rename branch? Target branch will be overwritten.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new b.M old-name existing-name"],
    related=["b.m", "b"],
)
def branch_move_force(args: list[str]) -> str:
    """Force rename a branch."""
    if len(args) >= 2:
        return f"git branch --move --force {' '.join(args[:2])}"
    return "git branch --move --force"


@command(
    short="b.v",
    category=CommandCategory.BRANCH,
    help="List branches with verbose output (upstream, last commit).",
    examples=["pigit cmd_new b.v", "pigit cmd_new b.v -r"],
    related=["b", "b.a"],
)
def branch_verbose(args: list[str]) -> str:
    """List branches verbosely."""
    return "git branch -vv"


@command(
    short="b.a",
    category=CommandCategory.BRANCH,
    help="List all branches (local and remote).",
    examples=["pigit cmd_new b.a", "pigit cmd_new b.a -vv"],
    related=["b", "b.v"],
)
def branch_all(args: list[str]) -> str:
    """List all branches including remote."""
    return "git branch --all -vv"


@command(
    short="b.o",
    category=CommandCategory.BRANCH,
    help="Checkout (switch to) a branch.",
    has_args=True,
    examples=["pigit cmd_new b.o main", "pigit cmd_new b.o -b new-branch"],
    related=["b.c", "b"],
)
def branch_checkout(args: list[str]) -> str:
    """Checkout a branch."""
    if not args:
        return "git checkout"
    return f"git checkout {' '.join(args)}"


# Aliases for backward compatibility
alias("bc", "b.c")
alias("bd", "b.d")
alias("bD", "b.D")
alias("bm", "b.m")
alias("bM", "b.M")
alias("bl", "b.v")
alias("bL", "b.a")
alias("co", "b.o")
