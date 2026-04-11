# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/submodule.py
Description: Submodule commands for cmd_new (S.* namespace).
Author: Project Team
Date: 2026-04-10
"""

from ._decorators import command, alias
from ._models import CommandCategory, SecurityLevel


@command(
    short="S",
    category=CommandCategory.SUBMODULE,
    help="Initialize, update or inspect submodules.",
    has_args=True,
    examples=["pigit cmd_new S", "pigit cmd_new S status"],
    related=["S.u", "S.a", "S.f"],
)
def submodule(args: list[str]) -> str:
    """Manage submodules."""
    base = "git submodule"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="S.a",
    category=CommandCategory.SUBMODULE,
    help="Add a submodule.",
    has_args=True,
    examples=["pigit cmd_new S.a https://github.com/user/repo.git path/to/sub"],
    related=["S", "S.f"],
)
def submodule_add(args: list[str]) -> str:
    """Add submodule."""
    base = "git submodule add"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="S.u",
    category=CommandCategory.SUBMODULE,
    help="Update submodules.",
    has_args=True,
    examples=["pigit cmd_new S.u", "pigit cmd_new S.u --init --recursive"],
    related=["S", "S.a"],
)
def submodule_update(args: list[str]) -> str:
    """Update submodules."""
    base = "git submodule update"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="S.f",
    category=CommandCategory.SUBMODULE,
    help="Deinit and remove submodule (force).",
    has_args=True,
    dangerous=True,
    confirm_msg="Remove submodule? This will delete submodule contents.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new S.f path/to/sub"],
    related=["S", "S.a"],
)
def submodule_force_remove(args: list[str]) -> str:
    """Force remove submodule."""
    if args:
        sub_path = args[0]
        # Multi-step removal
        cmds = [
            f"git submodule deinit -f {sub_path}",
            f"git rm -f {sub_path}",
            f"rm -rf .git/modules/{sub_path}",
        ]
        return "; ".join(cmds)
    return "git submodule deinit -f"


@command(
    short="S.s",
    category=CommandCategory.SUBMODULE,
    help="Show submodule summary.",
    has_args=True,
    examples=["pigit cmd_new S.s"],
    related=["S", "S.l"],
)
def submodule_summary(args: list[str]) -> str:
    """Show submodule summary."""
    base = "git submodule summary"
    if args:
        return f"{base} {' '.join(args)}"
    return base


# Aliases
alias("Sa", "S.a")
alias("Su", "S.u")
