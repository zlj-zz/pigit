"""
Module: pigit/app_command_palette.py
Description: Pigit command palette wiring with executable catalog entries.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from pigit.termui import widgets as termui_widgets
from pigit.termui.widgets import PaletteItem

# Priority order: navigation → network → quit → sequencer controls.
DEFAULT_COMMANDS: list[PaletteItem] = [
    PaletteItem("status", "Switch to Status"),
    PaletteItem("branch", "Switch to Branch"),
    PaletteItem("commit", "Switch to Commit"),
    PaletteItem("stash", "Focus Stash panel"),
    PaletteItem("push", "Push to upstream"),
    PaletteItem("pull", "Pull from upstream"),
    PaletteItem("fetch", "Fetch from remote"),
    PaletteItem("quit", "Quit Pigit"),
    PaletteItem("continue-merge", "Continue merge"),
    PaletteItem("rebase-continue", "Continue rebase"),
    PaletteItem("rebase-abort", "Abort rebase"),
    PaletteItem("rebase-skip", "Skip rebase step"),
    PaletteItem("cherry-pick-continue", "Continue cherry-pick"),
    PaletteItem("cherry-pick-abort", "Abort cherry-pick"),
    PaletteItem("cherry-pick-skip", "Skip cherry-pick"),
]

KNOWN_COMMAND_IDS: frozenset[str] = frozenset(item.id for item in DEFAULT_COMMANDS)


def catalog_for_context(sequencer: str | None) -> list[PaletteItem]:
    """Return priority-ordered commands for the current git sequencer state.

    Merge/rebase/cherry-pick controls appear only while that sequencer is
    active so the open list stays light.
    """
    out: list[PaletteItem] = []
    for item in DEFAULT_COMMANDS:
        if item.id == "continue-merge" and sequencer != "merge":
            continue
        if item.id.startswith("rebase-") and sequencer != "rebase":
            continue
        if item.id.startswith("cherry-pick-") and sequencer != "cherry-pick":
            continue
        out.append(item)
    return out


class CommandPalette(termui_widgets.CommandPalette):
    """Pigit-specific command palette backed by :data:`DEFAULT_COMMANDS`."""

    def __init__(
        self,
        on_execute: Callable[[str], None] | None = None,
        on_dismiss: Callable[[], None] | None = None,
        commands: Sequence[str | tuple[str, str] | PaletteItem] | None = None,
        **kwargs,
    ) -> None:
        if commands is None:
            items: Sequence[str | tuple[str, str] | PaletteItem] = DEFAULT_COMMANDS
        else:
            items = commands
        super().__init__(
            items=items,
            on_execute=on_execute,
            on_dismiss=on_dismiss,
            **kwargs,
        )
