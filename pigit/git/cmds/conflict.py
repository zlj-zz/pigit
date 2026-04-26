# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/conflict.py
Description: Conflict resolution commands for cmd_new (C.* namespace).
Author: Zev
Date: 2026-04-10
"""

from ._decorators import command, alias
from ._models import CommandCategory, SecurityLevel


@command(
    short="C",
    category=CommandCategory.CONFLICT,
    help="Show conflict status.",
    examples=["pigit cmd_new C"],
    related=["C.l", "C.d", "C.r"],
)
def conflict(args: list[str]) -> str:
    """Show conflicts."""
    return "git diff --name-only --diff-filter=U"


@command(
    short="C.l",
    category=CommandCategory.CONFLICT,
    help="List conflicted files.",
    examples=["pigit cmd_new C.l"],
    related=["C", "C.s"],
)
def conflict_list(args: list[str]) -> str:
    """List conflicted files."""
    return "git diff --name-only --diff-filter=U"


@command(
    short="C.d",
    category=CommandCategory.CONFLICT,
    help="Show conflict diff.",
    has_args=True,
    examples=["pigit cmd_new C.d", "pigit cmd_new C.d file.txt"],
    related=["C", "C.l"],
)
def conflict_diff(args: list[str]) -> str:
    """Show conflict diff."""
    base = "git diff"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="C.ours",
    category=CommandCategory.CONFLICT,
    help="Checkout our version of conflicted files.",
    has_args=True,
    dangerous=True,
    confirm_msg="Accept our version? Their changes will be lost.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new C.ours file.txt", "pigit cmd_new C.ours --all"],
    related=["C", "C.theirs"],
)
def conflict_ours(args: list[str]) -> str:
    """Accept our version."""
    if args:
        return f"git checkout --ours {' '.join(args)}"
    return "git checkout --ours"


@command(
    short="C.theirs",
    category=CommandCategory.CONFLICT,
    help="Checkout their version of conflicted files.",
    has_args=True,
    dangerous=True,
    confirm_msg="Accept their version? Our changes will be lost.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new C.theirs file.txt", "pigit cmd_new C.theirs --all"],
    related=["C", "C.ours"],
)
def conflict_theirs(args: list[str]) -> str:
    """Accept their version."""
    if args:
        return f"git checkout --theirs {' '.join(args)}"
    return "git checkout --theirs"


@command(
    short="C.mark",
    category=CommandCategory.CONFLICT,
    help="Mark file as resolved (add to index).",
    has_args=True,
    examples=["pigit cmd_new C.mark file.txt"],
    related=["C", "i"],
)
def conflict_mark(args: list[str]) -> str:
    """Mark resolved."""
    if args:
        return f"git add {' '.join(args)}"
    return "git add"


@command(
    short="C.tool",
    category=CommandCategory.CONFLICT,
    help="Launch merge tool.",
    has_args=True,
    examples=["pigit cmd_new C.tool", "pigit cmd_new C.tool file.txt"],
    related=["C", "C.d"],
)
def conflict_tool(args: list[str]) -> str:
    """Launch mergetool."""
    base = "git mergetool"
    if args:
        return f"{base} {' '.join(args)}"
    return base


# Aliases
alias("Cl", "C.l")
alias("Cd", "C.d")
