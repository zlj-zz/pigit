# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/push_pull.py
Description: Push and pull commands for cmd_new (p.*, f.* namespace).
Author: Project Team
Date: 2026-04-10
"""

from ._decorators import command, alias
from ._models import CommandCategory, SecurityLevel


# Push commands
@command(
    short="p",
    category=CommandCategory.PUSH,
    help="Push commits to remote.",
    has_args=True,
    examples=["pigit cmd_new p", "pigit cmd_new p origin main"],
    related=["p.f", "p.F", "f"],
)
def push(args: list[str]) -> str:
    """Push to remote."""
    base = "git push"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="p.f",
    category=CommandCategory.PUSH,
    help="Force push with lease (safe force push).",
    has_args=True,
    dangerous=True,
    confirm_msg="Force push? Ensure no one else has pushed.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new p.f", "pigit cmd_new p.f origin main"],
    related=["p", "p.F"],
)
def push_force(args: list[str]) -> str:
    """Force push with lease."""
    base = "git push --force-with-lease"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="p.F",
    category=CommandCategory.PUSH,
    help="Force push (destructive, no lease check).",
    has_args=True,
    dangerous=True,
    confirm_msg="Force push WITHOUT lease check? This may overwrite others' work!",
    security_level=SecurityLevel.DESTRUCTIVE,
    examples=["pigit cmd_new p.F origin main"],
    related=["p", "p.f"],
)
def push_force_destructive(args: list[str]) -> str:
    """Force push without lease."""
    base = "git push --force"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="p.u",
    category=CommandCategory.PUSH,
    help="Push and set upstream.",
    has_args=True,
    examples=["pigit cmd_new p.u origin feature-branch"],
    related=["p", "b.c"],
)
def push_upstream(args: list[str]) -> str:
    """Push with upstream."""
    base = "git push -u"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="p.d",
    category=CommandCategory.PUSH,
    help="Delete remote branch.",
    has_args=True,
    dangerous=True,
    confirm_msg="Delete remote branch?",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new p.d origin old-branch"],
    related=["b.d", "p"],
)
def push_delete(args: list[str]) -> str:
    """Delete remote branch."""
    if len(args) >= 2:
        return f"git push {args[0]} --delete {args[1]}"
    return "git push --delete"


@command(
    short="p.tags",
    category=CommandCategory.PUSH,
    help="Push all tags.",
    has_args=True,
    examples=["pigit cmd_new p.tags", "pigit cmd_new p.tags origin"],
    related=["t", "p"],
)
def push_tags(args: list[str]) -> str:
    """Push all tags."""
    if args:
        return f"git push {' '.join(args)} --tags"
    return "git push --tags"


# Fetch commands
@command(
    short="f",
    category=CommandCategory.FETCH,
    help="Fetch from remote.",
    has_args=True,
    examples=["pigit cmd_new f", "pigit cmd_new f origin"],
    related=["f.a", "f.p", "p"],
)
def fetch(args: list[str]) -> str:
    """Fetch from remote."""
    base = "git fetch"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="f.a",
    category=CommandCategory.FETCH,
    help="Fetch from all remotes.",
    examples=["pigit cmd_new f.a"],
    related=["f", "f.p"],
)
def fetch_all(args: list[str]) -> str:
    """Fetch all remotes."""
    return "git fetch --all"


@command(
    short="f.p",
    category=CommandCategory.FETCH,
    help="Prune deleted remote branches.",
    examples=["pigit cmd_new f.p", "pigit cmd_new f.a --prune"],
    related=["f", "f.a"],
)
def fetch_prune(args: list[str]) -> str:
    """Fetch and prune."""
    return "git fetch --prune"


@command(
    short="f.t",
    category=CommandCategory.FETCH,
    help="Fetch tags.",
    has_args=True,
    examples=["pigit cmd_new f.t", "pigit cmd_new f.t origin"],
    related=["f", "t"],
)
def fetch_tags(args: list[str]) -> str:
    """Fetch tags."""
    base = "git fetch --tags"
    if args:
        return f"{base} {' '.join(args)}"
    return base


# Aliases
alias("pf", "p.f")
alias("pF", "p.F")
alias("pu", "p.u")
alias("fa", "f.a")
alias("fp", "f.p")
