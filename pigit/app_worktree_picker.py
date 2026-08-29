"""
Module: pigit/app_worktree_picker.py
Description: Bottom-sheet UI for listing and switching git worktrees.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from pigit.ext.utils import split_at_most
from pigit.git.api import WorktreeInfo
from pigit.termui import (
    FeedbackKind,
    Segment,
    bind_action,
    dismiss_sheet,
    palette,
    show_toast,
)

from .app_list_picker import ListPickerSheet
from .app_theme import THEME


@dataclass(frozen=True)
class WorktreePickerEntry:
    """One selectable row in the worktree picker sheet."""

    info: WorktreeInfo
    is_current: bool = False


def format_worktree_row(
    info: WorktreeInfo,
    *,
    is_current: bool = False,
) -> list[Segment]:
    """Build TUI segments for one worktree row.

    Layout::

        ● path   branch|(detached)   short_sha
    """
    marker = "● " if is_current else "  "
    branch = "(detached)" if info.detached or not info.branch else info.branch
    short = info.head_sha[:7] if info.head_sha else "·"
    return [
        Segment(marker, fg=THEME.fg_success if is_current else THEME.fg_dim),
        Segment(info.path, fg=THEME.fg_header_repo, style_flags=palette.STYLE_BOLD),
        Segment("  ", fg=THEME.fg_dim),
        Segment(branch, fg=THEME.fg_accent),
        Segment("  ", fg=THEME.fg_dim),
        Segment(short, fg=THEME.fg_muted),
    ]


def build_worktree_picker_entries(
    worktrees: Sequence[WorktreeInfo],
    *,
    current_path: str,
) -> list[WorktreePickerEntry]:
    """Mark the session path as current (resolved path equality)."""
    current = _resolve_path(current_path)
    entries: list[WorktreePickerEntry] = []
    for info in worktrees:
        entries.append(
            WorktreePickerEntry(
                info=info,
                is_current=_resolve_path(info.path) == current,
            )
        )
    return entries


def parse_add_worktree_input(raw: str) -> tuple[str, str]:
    """Parse ``path [branch]``; default branch is ``wt-<basename>``.

    ``shlex`` honours quoted paths, so a path containing spaces must be
    quoted; an unquoted third token is an explicit error instead of a silent
    mis-split into ``path``/``branch``.
    """
    parts = split_at_most(raw, 2, "path [branch] (quote paths with spaces)")
    target = parts[0]
    if len(parts) == 2 and parts[1].strip():
        branch = parts[1].strip()
    else:
        name = Path(target).name or "worktree"
        branch = f"wt-{name}"
    return target, branch


def _resolve_path(path: str) -> str:
    try:
        return str(Path(path).resolve())
    except OSError:
        return path


class WorktreePickerSheet(ListPickerSheet):
    """Bottom sheet listing ``git worktree`` entries for session switch."""

    keymap_namespace = "worktree_picker"

    def __init__(
        self,
        *,
        entries: list[WorktreePickerEntry],
        on_switch: Callable[[str], None],
        on_add: Callable[[], None] | None = None,
        on_remove: Callable[[WorktreeInfo], None] | None = None,
        on_toggle_mode: Callable[[], None] | None = None,
        on_dismiss: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            entries=entries,
            on_switch=on_switch,
            on_toggle_mode=on_toggle_mode,
            on_dismiss=on_dismiss,
            empty_state=[
                Segment("  No worktrees", fg=THEME.fg_dim),
                Segment("press + to add", fg=THEME.fg_muted),
            ],
        )
        self._on_add = on_add
        self._on_remove = on_remove

    def get_footer_entries(self) -> list[tuple[str, str]]:
        """Hints while the worktree picker owns the keyboard."""
        return [
            ("w", "Repos"),
            ("+", "Add"),
            ("-", "Remove"),
            ("/", "Filter"),
            ("enter", "Switch"),
            ("esc", "Close"),
        ]

    def _row_segment_for(self, entry: WorktreePickerEntry) -> list[Segment]:
        return format_worktree_row(entry.info, is_current=entry.is_current)

    def _handle_entry(self, entry: WorktreePickerEntry) -> None:
        dismiss_sheet()
        if not entry.info.path:
            show_toast("Worktree path missing", duration=2.0, kind=FeedbackKind.ERROR)
            return
        self._on_switch(entry.info.path)

    @bind_action("add", "+", "=", desc="Add worktree", tip="Add")
    def add_worktree(self) -> None:
        """Prompt for a new worktree path and create it."""
        self._clear_double_click()
        if self._on_add is not None:
            self._on_add()

    @bind_action("remove", "-", desc="Remove selected worktree", tip="Remove")
    def remove_worktree(self) -> None:
        """Request removal of the highlighted worktree."""
        self._clear_double_click()
        entry = self._entry_at(self.curr_no)
        if entry is None:
            return
        if self._on_remove is not None:
            self._on_remove(entry.info)
