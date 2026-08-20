"""
Module: pigit/app_command_palette.py
Description: Pigit command palette wiring with default Git command names.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from collections.abc import Callable

from pigit.termui import widgets as termui_widgets

# Default command palette commands
DEFAULT_COMMANDS: list[str] = [
    "status",
    "branch",
    "commit",
    "diff",
    "log",
    "stash",
    "pull",
    "push",
    "fetch",
    "checkout",
    "merge",
    "rebase",
    "reset",
    "clean",
    "tag",
    "config",
    "help",
    "quit",
    "continue-merge",
    "rebase-continue",
    "rebase-abort",
    "rebase-skip",
    "cherry-pick-continue",
    "cherry-pick-abort",
    "cherry-pick-skip",
]


class CommandPalette(termui_widgets.CommandPalette):
    """Pigit-specific command palette backed by :data:`DEFAULT_COMMANDS`."""

    def __init__(
        self,
        on_execute: Callable[[str], None] | None = None,
        on_dismiss: Callable[[], None] | None = None,
        commands: list[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            items=list(commands) if commands is not None else list(DEFAULT_COMMANDS),
            on_execute=on_execute,
            on_dismiss=on_dismiss,
            **kwargs,
        )
