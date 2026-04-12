# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/rebase.py
Description: Rebase commands for cmd_new (rb.* namespace).
Author: Zev
Date: 2026-04-10
"""

from ._decorators import command, alias
from ._models import CommandCategory, SecurityLevel


@command(
    short="rb",
    category=CommandCategory.COMMIT,
    help="Rebase current branch onto another branch.",
    has_args=True,
    dangerous=True,
    confirm_msg="Rebase? This rewrites history.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new rb main", "pigit cmd_new rb --onto main feature"],
    related=["rb.c", "rb.a", "rb.i"],
)
def rebase(args: list[str]) -> str:
    """Rebase current branch."""
    base = "git rebase"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="rb.c",
    category=CommandCategory.COMMIT,
    help="Continue rebase after resolving conflicts.",
    examples=["pigit cmd_new rb.c"],
    related=["rb", "rb.a"],
)
def rebase_continue(args: list[str]) -> str:
    """Continue rebase."""
    return "git rebase --continue"


@command(
    short="rb.a",
    category=CommandCategory.COMMIT,
    help="Abort rebase and restore original branch.",
    dangerous=True,
    confirm_msg="Abort rebase? All progress will be lost.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new rb.a"],
    related=["rb", "rb.c"],
)
def rebase_abort(args: list[str]) -> str:
    """Abort rebase."""
    return "git rebase --abort"


@command(
    short="rb.s",
    category=CommandCategory.COMMIT,
    help="Skip current commit during rebase.",
    examples=["pigit cmd_new rb.s"],
    related=["rb", "rb.c"],
)
def rebase_skip(args: list[str]) -> str:
    """Skip current commit in rebase."""
    return "git rebase --skip"


@command(
    short="rb.i",
    category=CommandCategory.COMMIT,
    help="Interactive rebase (reorder, edit, squash commits).",
    has_args=True,
    dangerous=True,
    confirm_msg="Interactive rebase? This rewrites history.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new rb.i HEAD~5", "pigit cmd_new rb.i main"],
    related=["rb", "rb.c"],
)
def rebase_interactive(args: list[str]) -> str:
    """Interactive rebase."""
    base = "git rebase -i"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="rb.m",
    category=CommandCategory.COMMIT,
    help="Rebase with autosquash (merge fixup commits).",
    has_args=True,
    dangerous=True,
    confirm_msg="Rebase with autosquash? This rewrites history.",
    security_level=SecurityLevel.DANGEROUS,
    examples=["pigit cmd_new rb.m main", "pigit cmd_new rb.m -i HEAD~5"],
    related=["rb", "rb.i"],
)
def rebase_autosquash(args: list[str]) -> str:
    """Rebase with autosquash."""
    base = "git rebase --autosquash"
    if args:
        return f"{base} {' '.join(args)}"
    return base


# Aliases
alias("rbc", "rb.c")
alias("rba", "rb.a")
alias("rbs", "rb.s")
alias("rbi", "rb.i")
alias("rbm", "rb.m")
