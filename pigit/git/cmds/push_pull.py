# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/push_pull.py
Description: Push and pull commands for cmd_new (p.*, f.* namespace).
Author: Zev
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
    help="Push and set upstream for current branch.",
    has_args=True,
    examples=["pigit cmd_new p.u", "pigit cmd_new p.u origin feature-branch"],
    related=["p", "b.c"],
)
def push_upstream(args: list[str]) -> str:
    """Push with upstream."""
    if args:
        return f"git push -u {' '.join(args)}"
    # Without args: push current branch to origin with upstream
    return 'git push --set-upstream origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)"'


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


@command(
    short="f.m",
    category=CommandCategory.FETCH,
    help="Fetch and merge (pull).",
    has_args=True,
    examples=["pigit cmd_new f.m", "pigit cmd_new f.m origin main"],
    related=["f", "f.r", "p"],
)
def fetch_merge(args: list[str]) -> str:
    """Fetch and merge (pull)."""
    base = "git pull"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="f.r",
    category=CommandCategory.FETCH,
    help="Fetch and rebase (pull --rebase).",
    has_args=True,
    examples=["pigit cmd_new f.r", "pigit cmd_new f.r origin main"],
    related=["f", "f.m", "p"],
)
def fetch_rebase(args: list[str]) -> str:
    """Fetch and rebase (pull --rebase)."""
    base = "git pull --rebase"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="f.u",
    category=CommandCategory.FETCH,
    help="Update: fetch all remotes, prune, and fast-forward merge.",
    examples=["pigit cmd_new f.u"],
    related=["f", "f.a", "f.p"],
)
def fetch_update(args: list[str]) -> str:
    """Update: fetch all remotes, prune, and fast-forward merge."""
    return "git fetch --all --prune && git merge --ff-only @{u}"


@command(
    short="f.c",
    category=CommandCategory.FETCH,
    help="Clone a repository.",
    has_args=True,
    examples=[
        "pigit cmd_new f.c https://github.com/user/repo.git",
        "pigit cmd_new f.c https://github.com/user/repo.git my-dir",
    ],
    related=["f", "f.C"],
)
def fetch_clone(args: list[str]) -> str:
    """Clone a repository."""
    if args:
        return f"git clone {' '.join(args)}"
    return "git clone"


@command(
    short="f.C",
    category=CommandCategory.FETCH,
    help="Shallow clone (depth=1) for quick checkout.",
    has_args=True,
    examples=["pigit cmd_new f.C https://github.com/user/repo.git"],
    related=["f", "f.c"],
)
def fetch_clone_shallow(args: list[str]) -> str:
    """Shallow clone (depth=1)."""
    if args:
        return f"git clone --depth=1 {' '.join(args)}"
    return "git clone --depth=1"


# Aliases
alias("pf", "p.f")
alias("pF", "p.F")
alias("pu", "p.u")
alias("fa", "f.a")
alias("fp", "f.p")
alias("fm", "f.m")
alias("fr", "f.r")
alias("fu", "f.u")
alias("fc", "f.c")
alias("fC", "f.C")
