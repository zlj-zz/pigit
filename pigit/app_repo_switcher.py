"""
Module: pigit/app_repo_switcher.py
Description: Bottom-sheet UI for switching among ManagedRepos entries.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from pigit.termui import (
    FeedbackKind,
    Segment,
    dismiss_sheet,
    palette,
    show_toast,
)

from .app_list_picker import ListPickerSheet
from .app_theme import THEME

Kind = Literal["repo", "add_current"]


@dataclass
class RepoSwitcherEntry:
    """One selectable row in the repo switcher sheet."""

    kind: Kind
    name: str
    path: str
    meta: dict = field(default_factory=dict)
    is_current: bool = False


def format_repo_switcher_row(
    name: str,
    meta: dict,
    *,
    is_current: bool = False,
) -> list[Segment]:
    """Build TUI segments for one managed-repo row (fields from ``meta``).

    Layout::

        ● name   branch*+?  ↑a↓b   commit_msg

    Marker ``●`` marks the active session repo; otherwise two spaces.
    Dirty/staged/untracked markers follow the same glyphs as CLI ``repo ll``.
    """
    marker = "● " if is_current else "  "
    symbols = (
        f"{'*' if meta.get('dirty') else ''}"
        f"{'+' if meta.get('staged') else ''}"
        f"{'?' if meta.get('untracked') else ''}"
    )
    branch = str(meta.get("branch") or "")
    branch_part = f"{branch}{symbols}" if branch or symbols else "·"
    ahead = meta.get("ahead")
    behind = meta.get("behind")
    tracking = ""
    if ahead not in (None, "", "?"):
        try:
            if int(ahead) > 0:
                tracking += f"↑{ahead}"
        except (TypeError, ValueError):
            pass
    if behind not in (None, "", "?"):
        try:
            if int(behind) > 0:
                tracking += f"↓{behind}"
        except (TypeError, ValueError):
            pass
    if not tracking:
        tracking = "·"
    msg = str(meta.get("commit_msg") or "").strip()

    segs: list[Segment] = [
        Segment(marker, fg=THEME.fg_success if is_current else THEME.fg_dim),
        Segment(name, fg=THEME.fg_header_repo, style_flags=palette.STYLE_BOLD),
        Segment("  ", fg=THEME.fg_dim),
        Segment(branch_part, fg=THEME.fg_accent),
        Segment("  ", fg=THEME.fg_dim),
        Segment(tracking, fg=THEME.fg_muted),
    ]
    if msg:
        segs.append(Segment("  ", fg=THEME.fg_dim))
        segs.append(Segment(msg, fg=THEME.fg_dim))
    return segs


def format_add_current_row(path: str) -> list[Segment]:
    """Segments for the ``⊕ add current repo`` action row."""
    return [
        Segment("  ⊕ add current repo: ", fg=THEME.fg_info),
        Segment(path, fg=THEME.fg_muted),
    ]


def build_repo_switcher_entries(
    repos: dict[str, dict],
    *,
    current_path: str,
    cwd: str,
) -> list[RepoSwitcherEntry]:
    """Build ordered switcher rows from ``ManagedRepos.load_repos()`` data.

    Args:
        repos: Mapping of repo name → ``{"path": ..., "meta": ...}``.
        current_path: Absolute path of the active TUI session.
        cwd: Path offered by the add-current row when not already managed.
    """
    entries: list[RepoSwitcherEntry] = []
    managed_paths = {
        str(info.get("path") or "") for info in repos.values() if info.get("path")
    }
    if cwd and cwd not in managed_paths:
        entries.append(
            RepoSwitcherEntry(kind="add_current", name="", path=cwd, meta={})
        )
    for name, info in sorted(repos.items(), key=lambda item: item[0].lower()):
        path = str(info.get("path") or "")
        raw_meta = info.get("meta")
        meta: dict = raw_meta if isinstance(raw_meta, dict) else {}
        entries.append(
            RepoSwitcherEntry(
                kind="repo",
                name=name,
                path=path,
                meta=meta,
                is_current=bool(path) and path == current_path,
            )
        )
    return entries


class RepoSwitcherSheet(ListPickerSheet):
    """Bottom sheet listing managed repos for in-TUI session switch."""

    keymap_namespace = "repo_switcher"

    def __init__(
        self,
        *,
        entries: list[RepoSwitcherEntry],
        on_switch: Callable[[str], None],
        on_add_current: Callable[[str], None] | None = None,
        on_toggle_mode: Callable[[], None] | None = None,
        on_dismiss: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            entries=entries,
            on_switch=on_switch,
            on_toggle_mode=on_toggle_mode,
            on_dismiss=on_dismiss,
            empty_state=[
                Segment("  No managed repos", fg=THEME.fg_dim),
                Segment("add paths via `pigit repo add`", fg=THEME.fg_muted),
            ],
        )
        self._on_add_current = on_add_current

    def get_footer_entries(self) -> list[tuple[str, str]]:
        """Hints while the repo switcher owns the keyboard."""
        return [
            ("w", "Worktrees"),
            ("/", "Filter"),
            ("enter", "Switch"),
            ("esc", "Close"),
        ]

    def _row_segment_for(self, entry: RepoSwitcherEntry) -> list[Segment]:
        if entry.kind == "add_current":
            return format_add_current_row(entry.path)
        return format_repo_switcher_row(
            entry.name, entry.meta, is_current=entry.is_current
        )

    def _handle_entry(self, entry: RepoSwitcherEntry) -> None:
        dismiss_sheet()
        if entry.kind == "add_current":
            if self._on_add_current is not None:
                self._on_add_current(entry.path)
            return
        if not entry.path:
            show_toast("Repo path missing", duration=2.0, kind=FeedbackKind.ERROR)
            return
        self._on_switch(entry.path)
