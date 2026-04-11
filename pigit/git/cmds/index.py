# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/index.py
Description: Index/staging commands for cmd_new (i.* namespace).
Author: Project Team
Date: 2026-04-10
"""

from ._decorators import command, alias
from ._models import CommandCategory, SecurityLevel


@command(
    short="i",
    category=CommandCategory.INDEX,
    help="Add file contents to the index (stage files).",
    has_args=True,
    examples=["pigit cmd_new i", "pigit cmd_new i file.txt"],
    related=["i.a", "i.p", "i.r"],
)
def index(args: list[str]) -> str:
    """Stage files."""
    if not args:
        return "git add"
    return f"git add {' '.join(args)}"


@command(
    short="i.a",
    category=CommandCategory.INDEX,
    help="Add all changes to the index.",
    examples=["pigit cmd_new i.a", "pigit cmd_new i.a -A"],
    related=["i", "i.p"],
)
def index_all(args: list[str]) -> str:
    """Stage all changes."""
    return "git add --all"


@command(
    short="i.p",
    category=CommandCategory.INDEX,
    help="Add changes interactively (patch mode).",
    has_args=True,
    examples=["pigit cmd_new i.p", "pigit cmd_new i.p file.txt"],
    related=["i", "i.a"],
)
def index_patch(args: list[str]) -> str:
    """Stage interactively."""
    if args:
        return f"git add -p {' '.join(args)}"
    return "git add -p"


@command(
    short="i.u",
    category=CommandCategory.INDEX,
    help="Add only updated/modified files (not new files).",
    examples=["pigit cmd_new i.u"],
    related=["i", "i.a"],
)
def index_update(args: list[str]) -> str:
    """Stage only updated files."""
    return "git add -u"


@command(
    short="i.r",
    category=CommandCategory.INDEX,
    help="Reset (unstage) files from the index.",
    has_args=True,
    dangerous=True,
    confirm_msg="Unstage files? Changes will remain in working tree.",
    security_level=SecurityLevel.NORMAL,
    examples=["pigit cmd_new i.r", "pigit cmd_new i.r file.txt"],
    related=["i.R", "i"],
)
def index_reset(args: list[str]) -> str:
    """Unstage files."""
    if not args:
        return "git reset"
    return f"git reset -- {' '.join(args)}"


@command(
    short="i.R",
    category=CommandCategory.INDEX,
    help="Hard reset index and working tree.",
    has_args=True,
    dangerous=True,
    confirm_msg="Hard reset? Uncommitted changes WILL be lost!",
    security_level=SecurityLevel.DESTRUCTIVE,
    examples=["pigit cmd_new i.R", "pigit cmd_new i.R --hard"],
    related=["i.r", "i"],
)
def index_reset_hard(args: list[str]) -> str:
    """Hard reset."""
    if not args:
        return "git reset --hard"
    return f"git reset --hard {' '.join(args)}"


@command(
    short="i.d",
    category=CommandCategory.INDEX,
    help="Show differences between index and working tree.",
    has_args=True,
    examples=["pigit cmd_new i.d", "pigit cmd_new i.d --cached"],
    related=["i.ds", "w.d"],
)
def index_diff(args: list[str]) -> str:
    """Show index diff."""
    base = "git diff"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="i.ds",
    category=CommandCategory.INDEX,
    help="Show diff of staged changes.",
    has_args=True,
    examples=["pigit cmd_new i.ds", "pigit cmd_new i.ds --stat"],
    related=["i.d", "i"],
)
def index_diff_staged(args: list[str]) -> str:
    """Show staged diff."""
    base = "git diff --staged"
    if args:
        return f"{base} {' '.join(args)}"
    return base


# Aliases
alias("ia", "i.a")
alias("iA", "i.p")  # Interactive add
alias("ir", "i.r")
alias("iR", "i.R")
