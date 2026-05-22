"""
Module: pigit/handlers/cmd_picker_data.py
Description: Data adapter and context-aware sorting for cmd picker.
Author: Zev
Date: 2026-04-10
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterator
from typing import TYPE_CHECKING

from pigit.context import Context
from pigit.git.cmds._completion_types import CompletionType
from pigit.git.cmds._registry import get_registry


@dataclass
class CmdNewEntry:
    """Command entry for picker, adapted from CommandDef.

    Attributes:
        name: Command short name (e.g., 'b.c')
        help_text: Command help description
        category: Command category (e.g., 'branch', 'commit')
        is_dangerous: Whether command is marked as dangerous
        has_args: Whether command accepts arguments
        arg_completion: Optional argument completion type
    """

    name: str
    help_text: str
    category: str
    is_dangerous: bool
    has_args: bool
    arg_completion: CompletionType | None = None


def iter_cmd_new_entries() -> Iterator[CmdNewEntry]:
    """Iterate over all cmd_new commands for picker.

    Yields:
        CmdNewEntry for each registered command, sorted by name.
    """
    registry = get_registry()
    for cmd_def in sorted(registry.get_all(), key=lambda c: c.meta.short):
        meta = cmd_def.meta
        comp = meta.arg_completion
        if isinstance(comp, list) and comp:
            comp = comp[0]
        yield CmdNewEntry(
            name=meta.short,
            help_text=meta.help,
            category=meta.category.value,
            is_dangerous=meta.dangerous,
            has_args=meta.has_args,
            arg_completion=comp if isinstance(comp, CompletionType) else None,
        )


# ---------------------------------------------------------------------------
# Context-aware sorting
# ---------------------------------------------------------------------------


def build_context_signals() -> dict[str, bool]:
    """Detect working-tree context signals from current repo.

    Returns:
        Dict with keys has_unstaged, has_staged, has_conflict
    """
    signals = {
        "has_unstaged": False,
        "has_staged": False,
        "has_conflict": False,
    }
    ctx = Context.try_current()
    if ctx is None:
        return signals
    try:
        files = ctx.local_git.load_status()
    except Exception:
        return signals

    for f in files:
        if f.has_unstaged_change or not f.tracked:
            signals["has_unstaged"] = True
        if f.has_staged_change:
            signals["has_staged"] = True
        if f.has_merged_conflicts:
            signals["has_conflict"] = True
    return signals


def context_score(entry: CmdNewEntry, signals: dict[str, bool]) -> int:
    """Compute context-aware priority score for an entry.

    Args:
        entry: Command entry
        signals: Context signals from build_context_signals

    Returns:
        Priority score (higher = more relevant)
    """
    cat = entry.category.lower()
    score = 0
    if signals.get("has_unstaged") and cat == "index":
        score += 100
    if signals.get("has_staged") and cat == "commit":
        score += 100
    if signals.get("has_conflict") and cat in ("conflict", "merge"):
        score += 100
    return score


def sort_picker_entries(
    entries: list[CmdNewEntry],
    mru: list[str],
    signals: dict[str, bool],
) -> list[CmdNewEntry]:
    """Sort entries by MRU, context relevance, then name.

    Args:
        entries: Command entries
        mru: MRU command names in order
        signals: Context signals

    Returns:
        Sorted entries
    """
    mru_index = {name: idx for idx, name in enumerate(mru)}

    def sort_key(e: CmdNewEntry) -> tuple[int, int, str]:
        return (
            mru_index.get(e.name, 999),
            -context_score(e, signals),
            e.name,
        )

    return sorted(entries, key=sort_key)
