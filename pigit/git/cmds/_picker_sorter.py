# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_picker_sorter.py
Description: Context-aware sorting for picker command entries.
Author: Zev
Date: 2026-04-15
"""

from typing import TYPE_CHECKING

from pigit.context import Context

if TYPE_CHECKING:
    from ._picker_adapter import CmdNewEntry


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
        files = ctx.repo.load_status()
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


def context_score(entry: "CmdNewEntry", signals: dict[str, bool]) -> int:
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
    entries: list["CmdNewEntry"],
    mru: list[str],
    signals: dict[str, bool],
) -> list["CmdNewEntry"]:
    """Sort entries by MRU, context relevance, then name.

    Args:
        entries: Command entries
        mru: MRU command names in order
        signals: Context signals

    Returns:
        Sorted entries
    """
    mru_index = {name: idx for idx, name in enumerate(mru)}

    def sort_key(e: "CmdNewEntry") -> tuple[int, int, str]:
        return (
            mru_index.get(e.name, 999),
            -context_score(e, signals),
            e.name,
        )

    return sorted(entries, key=sort_key)
