# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/remote.py
Description: Remote commands for cmd_new (r.* namespace).
Author: Project Team
Date: 2026-04-10
"""

from ._decorators import command, alias
from ._models import CommandCategory, SecurityLevel


@command(
    short="r",
    category=CommandCategory.REMOTE,
    help="Manage remote repositories.",
    has_args=True,
    examples=["pigit cmd_new r", "pigit cmd_new r -v"],
    related=["r.v", "r.a", "r.u"],
)
def remote(args: list[str]) -> str:
    """Manage remotes."""
    base = "git remote"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="r.v",
    category=CommandCategory.REMOTE,
    help="Show remote URLs.",
    examples=["pigit cmd_new r.v", "pigit cmd_new r.v -v"],
    related=["r", "r.s"],
)
def remote_verbose(args: list[str]) -> str:
    """Show remotes with URLs."""
    return "git remote -v"


@command(
    short="r.a",
    category=CommandCategory.REMOTE,
    help="Add a remote.",
    has_args=True,
    examples=["pigit cmd_new r.a origin https://github.com/user/repo.git"],
    related=["r", "r.rm"],
)
def remote_add(args: list[str]) -> str:
    """Add remote."""
    if len(args) >= 2:
        return f"git remote add {' '.join(args[:2])}"
    return "git remote add"


@command(
    short="r.rm",
    category=CommandCategory.REMOTE,
    help="Remove a remote.",
    has_args=True,
    dangerous=True,
    confirm_msg="Remove remote?",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new r.rm old-remote"],
    related=["r", "r.a"],
)
def remote_remove(args: list[str]) -> str:
    """Remove remote."""
    if args:
        return f"git remote remove {' '.join(args)}"
    return "git remote remove"


@command(
    short="r.rn",
    category=CommandCategory.REMOTE,
    help="Rename a remote.",
    has_args=True,
    examples=["pigit cmd_new r.rn old-name new-name"],
    related=["r", "r.a"],
)
def remote_rename(args: list[str]) -> str:
    """Rename remote."""
    if len(args) >= 2:
        return f"git remote rename {' '.join(args[:2])}"
    return "git remote rename"


@command(
    short="r.u",
    category=CommandCategory.REMOTE,
    help="Update remote branches.",
    has_args=True,
    examples=["pigit cmd_new r.u", "pigit cmd_new r.u origin"],
    related=["f", "r"],
)
def remote_update(args: list[str]) -> str:
    """Update remote."""
    base = "git remote update"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="r.s",
    category=CommandCategory.REMOTE,
    help="Show remote information.",
    has_args=True,
    examples=["pigit cmd_new r.s origin"],
    related=["r", "r.v"],
)
def remote_show(args: list[str]) -> str:
    """Show remote info."""
    base = "git remote show"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="r.prune",
    category=CommandCategory.REMOTE,
    help="Prune stale remote-tracking branches.",
    has_args=True,
    dangerous=True,
    confirm_msg="Prune stale remote branches?",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new r.prune", "pigit cmd_new r.prune origin"],
    related=["f.p", "r"],
)
def remote_prune(args: list[str]) -> str:
    """Prune remote branches."""
    base = "git remote prune"
    if args:
        return f"{base} {' '.join(args)}"
    return base


# Aliases
alias("rv", "r.v")
alias("ra", "r.a")
alias("rrm", "r.rm")
alias("rrn", "r.rn")
alias("ru", "r.u")
alias("rs", "r.s")
