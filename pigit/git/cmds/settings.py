# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/settings.py
Description: Git settings commands for cmd_new (set.* namespace).
Author: Zev
Date: 2026-04-10
"""

from ._decorators import command, alias
from ._models import CommandCategory, SecurityLevel


@command(
    short="set",
    category=CommandCategory.SETTINGS,
    help="Get or set git configuration.",
    has_args=True,
    examples=["pigit cmd_new set user.name", "pigit cmd_new set user.name 'John Doe'"],
    related=["set.l", "set.g", "set.e"],
)
def settings(args: list[str]) -> str:
    """Get/set git config."""
    if not args:
        return "git config --list"
    if len(args) == 1:
        return f"git config {args[0]}"
    return f"git config {' '.join(args)}"


@command(
    short="set.l",
    category=CommandCategory.SETTINGS,
    help="List all git configuration.",
    has_args=True,
    examples=["pigit cmd_new set.l", "pigit cmd_new set.l --local"],
    related=["set", "set.g"],
)
def settings_list(args: list[str]) -> str:
    """List config."""
    base = "git config --list"
    if args:
        return f"{base} {' '.join(args)}"
    return base


@command(
    short="set.g",
    category=CommandCategory.SETTINGS,
    help="Get a config value.",
    has_args=True,
    examples=["pigit cmd_new set.g user.email"],
    related=["set", "set.l"],
)
def settings_get(args: list[str]) -> str:
    """Get config value."""
    if args:
        return f"git config {args[0]}"
    return "git config"


@command(
    short="set.e",
    category=CommandCategory.SETTINGS,
    help="Edit git config file.",
    examples=["pigit cmd_new set.e", "pigit cmd_new set.e --global"],
    related=["set", "set.l"],
)
def settings_edit(args: list[str]) -> str:
    """Edit config."""
    base = "git config --edit"
    if args:
        return f"{base} {' '.join(args)}"
    return base


# Aliases
alias("setl", "set.l")
alias("setg", "set.g")
alias("sete", "set.e")
