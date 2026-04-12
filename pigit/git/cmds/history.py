# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/history.py
Description: History, log, stash, and tag commands for cmd_new (l.*, s.*, t.* namespace).
Author: Zev
Date: 2026-04-10
"""

from ._decorators import command, alias
from ._models import CommandCategory, SecurityLevel


# Log commands
@command(
    short="l",
    category=CommandCategory.LOG,
    help="Show commit log.",
    has_args=True,
    examples=["pigit cmd_new l", "pigit cmd_new l -5"],
    related=["l.o", "l.g", "l.s"],
)
def log(args: list[str]) -> str:
    """Show commit log."""
    base = "git log"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="l.o",
    category=CommandCategory.LOG,
    help="Show one-line log.",
    has_args=True,
    examples=["pigit cmd_new l.o", "pigit cmd_new l.o --graph"],
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
    examples=["pigit cmd_new l.g", "pigit cmd_new l.g --all"],
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
    examples=["pigit cmd_new l.s", "pigit cmd_new l.s -3"],
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
    examples=["pigit cmd_new l.p", "pigit cmd_new l.p -1"],
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
    examples=["pigit cmd_new l.c", "pigit cmd_new l.c -n 10"],
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
    examples=["pigit cmd_new s", "pigit cmd_new s push -m 'WIP'"],
    related=["s.l", "s.p", "s.d"],
)
def stash(args: list[str]) -> str:
    """Stash changes."""
    base = "git stash"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="s.l",
    category=CommandCategory.STASH,
    help="List stashes.",
    examples=["pigit cmd_new s.l"],
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
    examples=["pigit cmd_new s.p", "pigit cmd_new s.p stash@{1}"],
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
    examples=["pigit cmd_new s.a", "pigit cmd_new s.a stash@{0}"],
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
    dangerous=True,
    confirm_msg="Drop stash? Changes will be lost.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new s.d stash@{0}"],
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
    examples=["pigit cmd_new s.c"],
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
    examples=["pigit cmd_new s.s", "pigit cmd_new s.s -p"],
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
    examples=["pigit cmd_new t", "pigit cmd_new t v1.0.0"],
    related=["t.a", "t.d", "t.p"],
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
    examples=["pigit cmd_new t.a v1.0.0 -m 'Version 1.0.0'"],
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
    dangerous=True,
    confirm_msg="Delete tag?",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new t.d v1.0.0"],
    related=["t", "t.a"],
)
def tag_delete(args: list[str]) -> str:
    """Delete tag."""
    base = "git tag -d"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="t.p",
    category=CommandCategory.TAG,
    help="Push tags to remote.",
    has_args=True,
    examples=["pigit cmd_new t.p", "pigit cmd_new t.p origin v1.0.0"],
    related=["t", "p.tags"],
)
def tag_push(args: list[str]) -> str:
    """Push tags."""
    if args:
        return f"git push {' '.join(args)} --tags"
    return "git push --tags"


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
