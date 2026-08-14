"""
Module: pigit/git/cmds/history.py
Description: History, log, stash, and tag commands for cmd_new (l.*, s.*, t.* namespace).
Author: Zev
Date: 2026-04-10
"""

from __future__ import annotations

from ._decorators import command, alias
from ._models import CommandCategory, SecurityLevel
from ._completion_types import CompletionType


# Log commands
@command(
    short="l",
    category=CommandCategory.LOG,
    help="Show commit log.",
    has_args=True,
    examples=["pigit cmd l", "pigit cmd l -5"],
    related=["l.o", "l.g", "l.s"],
)
def log(args: list[str]) -> str:
    """Show commit log."""
    base = "git log --decorate --graph"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="l.o",
    category=CommandCategory.LOG,
    help="Show one-line log.",
    has_args=True,
    examples=["pigit cmd l.o", "pigit cmd l.o --graph"],
    related=["l", "l.g"],
)
def log_oneline(args: list[str]) -> str:
    """Show one-line log."""
    base = "git log --oneline --decorate"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="l.g",
    category=CommandCategory.LOG,
    help="Show log with graph.",
    has_args=True,
    examples=["pigit cmd l.g", "pigit cmd l.g --all"],
    related=["l", "l.o"],
)
def log_graph(args: list[str]) -> str:
    """Show log with graph."""
    base = "git log --oneline --graph --decorate"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="l.s",
    category=CommandCategory.LOG,
    help="Show log with stats.",
    has_args=True,
    examples=["pigit cmd l.s", "pigit cmd l.s -3"],
    related=["l", "l.p"],
)
def log_stat(args: list[str]) -> str:
    """Show log with stats."""
    base = "git log --stat"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="l.p",
    category=CommandCategory.LOG,
    help="Show log with patches.",
    has_args=True,
    examples=["pigit cmd l.p", "pigit cmd l.p -1"],
    related=["l", "l.s"],
)
def log_patch(args: list[str]) -> str:
    """Show log with patches."""
    base = "git log -p"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="l.c",
    category=CommandCategory.LOG,
    help="Show contributor statistics (commit count per contributor).",
    has_args=True,
    examples=["pigit cmd l.c", "pigit cmd l.c -n 10"],
    related=["l", "l.s"],
)
def log_contributors(args: list[str]) -> str:
    """Show contributor statistics."""
    base = "git shortlog --summary --numbered"
    if args:
        return f"{base} {' '.join(args)}"
    return base


# Stash commands
@command(
    short="s",
    category=CommandCategory.STASH,
    help="Stash changes.",
    has_args=True,
    examples=["pigit cmd s", "pigit cmd s push -m 'WIP'"],
    related=["s.l", "s.p", "s.d"],
)
def stash(args: list[str]) -> str:
    """Stash changes."""
    base = "git stash --include-untracked"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="s.l",
    category=CommandCategory.STASH,
    help="List stashes.",
    examples=["pigit cmd s.l"],
    related=["s", "s.s"],
)
def stash_list(args: list[str]) -> str:
    """List stashes."""
    return "git stash list"


@command(
    short="s.p",
    category=CommandCategory.STASH,
    help="Pop stash (apply and remove).",
    has_args=True,
    arg_completion=[CompletionType.STASH],
    examples=["pigit cmd s.p", "pigit cmd s.p stash@{1}"],
    related=["s", "s.a"],
)
def stash_pop(args: list[str]) -> str:
    """Pop stash."""
    base = "git stash pop"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="s.a",
    category=CommandCategory.STASH,
    help="Apply stash (keep in stash list).",
    has_args=True,
    arg_completion=[CompletionType.STASH],
    examples=["pigit cmd s.a", "pigit cmd s.a stash@{0}"],
    related=["s", "s.p"],
)
def stash_apply(args: list[str]) -> str:
    """Apply stash."""
    base = "git stash apply"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="s.d",
    category=CommandCategory.STASH,
    help="Drop a stash.",
    has_args=True,
    arg_completion=[CompletionType.STASH],
    dangerous=True,
    confirm_msg="Drop stash? Changes will be lost.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd s.d stash@{0}"],
    related=["s", "s.c"],
)
def stash_drop(args: list[str]) -> str:
    """Drop stash."""
    base = "git stash drop"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="s.c",
    category=CommandCategory.STASH,
    help="Clear all stashes.",
    dangerous=True,
    confirm_msg="Clear ALL stashes? This cannot be undone!",
    security_level=SecurityLevel.DESTRUCTIVE,
    examples=["pigit cmd s.c"],
    related=["s", "s.d"],
)
def stash_clear(args: list[str]) -> str:
    """Clear all stashes."""
    return "git stash clear"


@command(
    short="s.s",
    category=CommandCategory.STASH,
    help="Show stash diff.",
    has_args=True,
    examples=["pigit cmd s.s", "pigit cmd s.s -p"],
    related=["s", "s.l"],
)
def stash_show(args: list[str]) -> str:
    """Show stash."""
    base = "git stash show --stat"
    if args:
        return f"{base} {' '.join(args)}"
    return base


# Tag commands
@command(
    short="t",
    category=CommandCategory.TAG,
    help="List or create tags.",
    has_args=True,
    examples=["pigit cmd t", "pigit cmd t v1.0.0"],
    related=["t.a", "t.d"],
)
def tag(args: list[str]) -> str:
    """Manage tags."""
    base = "git tag"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="t.a",
    category=CommandCategory.TAG,
    help="Create an annotated tag.",
    has_args=True,
    examples=["pigit cmd t.a v1.0.0 -m 'Version 1.0.0'"],
    related=["t", "t.d"],
)
def tag_annotated(args: list[str]) -> str:
    """Create annotated tag."""
    base = "git tag -a"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="t.d",
    category=CommandCategory.TAG,
    help="Delete a tag.",
    has_args=True,
    arg_completion=[CompletionType.TAG],
    dangerous=True,
    confirm_msg="Delete tag?",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd t.d v1.0.0"],
    related=["t", "t.a"],
)
def tag_delete(args: list[str]) -> str:
    """Delete tag."""
    base = "git tag -d"
    if args:
        return f"{base} {' '.join(args)}"
    return base


# Aliases
alias("lo", "l.o")
alias("lg", "l.g")
alias("ls", "l.s")
alias("lp", "l.p")
alias("lc", "l.c")
alias("sl", "s.l")
alias("sp", "s.p")
alias("sa", "s.a")
alias("sd", "s.d")
alias("ta", "t.a")
alias("td", "t.d")
