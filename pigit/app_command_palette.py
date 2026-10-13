"""
Module: pigit/app_command_palette.py
Description: The parameterized half of the command palette catalog.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from pigit.ext.utils import relative_time
from pigit.termui.widgets import PaletteArgs, PaletteItem

if TYPE_CHECKING:
    from pigit.git.model import ReflogEntry

# Commands that take an argument, and so cannot be derived from a binding: they
# need candidate completion and the palette's "id arg" input mode. Every other
# entry comes from the app's own bindings -- see
# ``PigitApplication.collect_binding_groups``, which is also what the Help
# panel reads.


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
                if rest.lower() in f"{e.sha} {e.refish} {e.message}".lower()
            ],
        ),
    ),
]

PARAMETERIZED_ACTIONS: frozenset[str] = frozenset(i.id for i in PARAMETERIZED_ITEMS)


def with_parameterized(
    items: Sequence[PaletteItem],
    *,
    branch_names: Callable[[], list[str]],
    file_names: Callable[[], list[str]],
    reflog_entries: Callable[[], list[ReflogEntry]] = lambda: [],
) -> list[PaletteItem]:
    """Return *items* followed by the parameterized commands.

    Their ``args.fetch`` closures call the accessors lazily on every keystroke.
    All three are reassigned on each call so a stale closure can never survive
    a later rebuild.
    """
    _ACCESSORS.branch_names = branch_names
    _ACCESSORS.file_names = file_names
    _ACCESSORS.reflog_entries = reflog_entries
    return list(items) + PARAMETERIZED_ITEMS
