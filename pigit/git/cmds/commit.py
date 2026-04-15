# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/commit.py
Description: Commit commands for cmd_new (c.* namespace).
Author: Zev
Date: 2026-04-10
"""

from ._decorators import command, alias
from ._models import CommandCategory, SecurityLevel
from ._completion_types import CompletionType


@command(
    short="c",
    category=CommandCategory.COMMIT,
    help="Record changes to the repository.",
    has_args=True,
    examples=["pigit cmd_new c -m 'message'", "pigit cmd_new c --amend"],
    related=["c.a", "c.m", "c.F"],
)
def commit(args: list[str]) -> str:
    """Create a commit."""
    if not args:
        return "git commit"
    return f"git commit {' '.join(args)}"


@command(
    short="c.a",
    category=CommandCategory.COMMIT,
    help="Commit all modified files.",
    has_args=True,
    examples=["pigit cmd_new c.a", "pigit cmd_new c.a -m 'message'"],
    related=["c", "c.m"],
)
def commit_all(args: list[str]) -> str:
    """Commit all changes."""
    base = "git commit -a"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="c.m",
    category=CommandCategory.COMMIT,
    help="Commit with a message.",
    has_args=True,
    examples=["pigit cmd_new c.m 'Initial commit'"],
    related=["c", "c.a"],
)
def commit_message(args: list[str]) -> str:
    """Commit with message."""
    if args:
        return f"git commit -m {' '.join(args)}"
    return "git commit"


@command(
    short="c.f",
    category=CommandCategory.COMMIT,
    help="Amend the last commit reusing the same log message as HEAD.",
    dangerous=True,
    confirm_msg="Amend last commit reusing HEAD message? This rewrites history.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new c.f"],
    related=["c.F", "c"],
)
def commit_fixup(args: list[str]) -> str:
    """Amend last commit reusing HEAD message (equivalent to cf in old system)."""
    return "git commit --amend --reuse-message HEAD"


@command(
    short="c.F",
    category=CommandCategory.COMMIT,
    help="Amend the previous commit with verbose output.",
    has_args=True,
    dangerous=True,
    confirm_msg="Amend last commit? This rewrites history.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new c.F", "pigit cmd_new c.F --no-edit"],
    related=["c.f", "c"],
)
def commit_amend(args: list[str]) -> str:
    """Amend last commit with verbose output (equivalent to cF in old system)."""
    base = "git commit --verbose --amend"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="c.fix",
    category=CommandCategory.COMMIT,
    help="Create a fixup commit (for autosquash rebase).",
    has_args=True,
    arg_completion=CompletionType.COMMIT,
    examples=["pigit cmd_new c.fix HEAD~1", "pigit cmd_new c.fix abc123"],
    related=["c", "c.s"],
)
def commit_fixup_target(args: list[str]) -> str:
    """Create fixup commit targeting a specific commit."""
    if args:
        return f"git commit --fixup {' '.join(args)}"
    return "git commit --fixup"


@command(
    short="c.s",
    category=CommandCategory.COMMIT,
    help="Create a squash commit (for autosquash rebase).",
    has_args=True,
    arg_completion=CompletionType.COMMIT,
    examples=["pigit cmd_new c.s HEAD~1", "pigit cmd_new c.s abc123"],
    related=["c", "c.fix"],
)
def commit_squash(args: list[str]) -> str:
    """Create squash commit targeting a specific commit."""
    if args:
        return f"git commit --squash {' '.join(args)}"
    return "git commit --squash"


@command(
    short="c.o",
    category=CommandCategory.COMMIT,
    help="Checkout a branch or paths.",
    has_args=True,
    arg_completion=CompletionType.REF,
    examples=["pigit cmd_new c.o main", "pigit cmd_new c.o -- file.txt"],
    related=["b.o", "c"],
)
def commit_checkout(args: list[str]) -> str:
    """Checkout branch or paths."""
    if not args:
        return "git checkout"
    return f"git checkout {' '.join(args)}"


@command(
    short="c.O",
    category=CommandCategory.COMMIT,
    help="Checkout interactively.",
    has_args=True,
    examples=["pigit cmd_new c.O -p"],
    related=["c.o", "c"],
)
def commit_checkout_interactive(args: list[str]) -> str:
    """Interactive checkout."""
    base = "git checkout -p"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="c.R",
    category=CommandCategory.COMMIT,
    help="Revert/undo the last commit (soft reset).",
    has_args=True,
    dangerous=True,
    confirm_msg="Undo last commit? Changes will be preserved in working tree.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new c.R", "pigit cmd_new c.R --hard"],
    related=["c.F", "c"],
)
def commit_undo(args: list[str]) -> str:
    """Undo last commit (soft reset)."""
    return "git reset --soft HEAD~1"


@command(
    short="c.empty",
    category=CommandCategory.COMMIT,
    help="Create an empty commit.",
    has_args=True,
    examples=["pigit cmd_new c.empty -m 'Trigger CI'"],
    related=["c", "c.m"],
)
def commit_empty(args: list[str]) -> str:
    """Create empty commit."""
    base = "git commit --allow-empty"
    if args:
        return f"{base} {' '.join(args)}"
    return base


# Aliases
alias("ca", "c.a")
alias("cm", "c.m")
alias("cf", "c.f")
alias("cF", "c.F")
alias("cO", "c.O")
