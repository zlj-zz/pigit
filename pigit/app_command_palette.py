"""
Module: pigit/app_command_palette.py
Description: Pigit command palette wiring with executable catalog entries.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from pigit.ext.utils import relative_time
from pigit.termui import widgets as termui_widgets
from pigit.termui.widgets import PaletteArgs, PaletteItem

if TYPE_CHECKING:
    from pigit.git.model import ReflogEntry

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


class _CatalogAccessors:
    """Late-bound name sources for parameterized ``args.fetch`` closures."""

    branch_names: Callable[[], list[str]] = staticmethod(lambda: [])
    file_names: Callable[[], list[str]] = staticmethod(lambda: [])
    reflog_entries: Callable[[], list[ReflogEntry]] = staticmethod(lambda: [])


_ACCESSORS = _CatalogAccessors()

PARAMETERIZED_ITEMS: list[PaletteItem] = [
    PaletteItem(
        "checkout",
        "Checkout branch",
        args=PaletteArgs(
            label="<Branch>",
            fetch=lambda rest: [
                b for b in _ACCESSORS.branch_names() if rest.lower() in b.lower()
            ],
        ),
    ),
    PaletteItem(
        "merge",
        "Merge branch",
        args=PaletteArgs(
            label="<Branch>",
            fetch=lambda rest: [
                b for b in _ACCESSORS.branch_names() if rest.lower() in b.lower()
            ],
        ),
    ),
    PaletteItem(
        "stage",
        "Stage file",
        args=PaletteArgs(
            label="<File>",
            fetch=lambda rest: [
                f for f in _ACCESSORS.file_names() if rest.lower() in f.lower()
            ],
        ),
    ),
    PaletteItem(
        "gitignore",
        "Ignore file",
        args=PaletteArgs(
            label="<File>",
            fetch=lambda rest: [
                f for f in _ACCESSORS.file_names() if rest.lower() in f.lower()
            ],
        ),
    ),
    PaletteItem(
        "reflog",
        "Recover from reflog",
        args=PaletteArgs(
            label="<Entry>",
            fetch=lambda rest: [
                (e.sha, f"{e.sha[:7]} {e.message} · {relative_time(e.when)}")
                for e in _ACCESSORS.reflog_entries()
                if rest.lower()
                in f"{e.sha} {e.refish} {e.message}".lower()
            ],
        ),
    ),
]

PARAMETERIZED_ACTIONS: frozenset[str] = frozenset(i.id for i in PARAMETERIZED_ITEMS)


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


def build_catalog(
    sequencer: str | None,
    *,
    branch_names: Callable[[], list[str]],
    file_names: Callable[[], list[str]],
    reflog_entries: Callable[[], list[ReflogEntry]] = lambda: [],
) -> list[PaletteItem]:
    """Return static context catalog plus parameterized command entries.

    Static sequencer filtering is unchanged. Parameterized items always appear;
    their ``args.fetch`` closures call the accessors lazily on each keystroke.
    All accessors are reassigned on every call so a stale closure can never
    survive a later catalog rebuild.
    """
    _ACCESSORS.branch_names = branch_names
    _ACCESSORS.file_names = file_names
    _ACCESSORS.reflog_entries = reflog_entries
    return catalog_for_context(sequencer) + PARAMETERIZED_ITEMS


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
