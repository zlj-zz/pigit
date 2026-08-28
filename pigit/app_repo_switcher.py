"""
Module: pigit/app_repo_switcher.py
Description: Bottom-sheet UI for switching among ManagedRepos entries.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from pigit.termui import (
    FeedbackKind,
    Segment,
    bind_action,
    dismiss_sheet,
    keys,
    palette,
    show_toast,
)
from pigit.termui.mouse import MouseEvent
from pigit.termui.viewport_hit import DOUBLE_CLICK_MS
from pigit.termui.widgets import OptionList

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


class RepoSwitcherSheet(OptionList):
    """Bottom sheet listing managed repos for in-TUI session switch."""

    CURSOR = "●"
    keymap_namespace = "repo_switcher"

    def __init__(
        self,
        *,
        entries: list[RepoSwitcherEntry],
        on_switch: Callable[[str], None],
        on_add_current: Callable[[str], None] | None = None,
        on_dismiss: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            empty_state=[
                Segment("  No managed repos", fg=THEME.fg_dim),
                Segment("add paths via `pigit repo add`", fg=THEME.fg_muted),
            ],
            on_search_changed=self._sync_filter,
        )
        self._entries = list(entries)
        self._on_switch = on_switch
        self._on_add_current = on_add_current
        self._on_dismiss = on_dismiss
        self._last_click_index: int | None = None
        self._last_click_time: float = 0.0
        self._row_segments: list[list[Segment]] = []
        self._rebuild_rows()

    def preferred_sheet_height(self, term_h: int) -> int:
        """Prefer up to 14 rows; host clamps to the sheet max fraction."""
        return min(14, max(6, len(self._entries) + 2))

    def mount(self) -> None:
        super().mount()

    def _rebuild_rows(self) -> None:
        self._row_segments = []
        texts: list[str] = []
        for entry in self._entries:
            if entry.kind == "add_current":
                segs = format_add_current_row(entry.path)
            else:
                segs = format_repo_switcher_row(
                    entry.name, entry.meta, is_current=entry.is_current
                )
            self._row_segments.append(segs)
            texts.append("".join(seg.text for seg in segs))
        self.set_source_content(texts)

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
        sub_row: int = 0,
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        """Paint pre-built switcher segments for the visible row."""
        source_idx = self.visible_to_source(idx)
        if 0 <= source_idx < len(self._row_segments):
            return ([], self._row_segments[source_idx], [])
        return super().describe_row(idx, is_cursor, item_idx=item_idx, sub_row=sub_row)

    @bind_action("next", "j", "down", desc="Next repo", tip="Navigate")
    def next(self, step: int = 1) -> None:
        self._clear_double_click()
        super().next(step)

    @bind_action("previous", "k", "up", desc="Previous repo", tip="Navigate")
    def previous(self, step: int = 1) -> None:
        self._clear_double_click()
        super().previous(step)

    @bind_action("filter", "/", desc="Filter repos", tip="Filter")
    def start_filter(self) -> None:
        """Enter incremental filter mode."""
        self._clear_double_click()
        self.enter_search()

    def capture_key(self, key: str) -> bool:
        """Route keys into filter mode while active."""
        return self.search_handle_key(key)

    def _sync_filter(self) -> None:
        """Apply the search query as a substring filter over row text."""
        self.set_filter(self.search_query)

    @bind_action(
        "confirm", keys.KEY_ENTER, desc="Switch to selected repo", tip="Switch"
    )
    def confirm(self) -> None:
        """Activate the highlighted row (switch or add-current)."""
        self._activate_index(self.curr_no)

    @bind_action("close", "@", "esc", desc="Close switcher", tip="Close")
    def close(self) -> None:
        """Dismiss the switcher sheet."""
        self._clear_double_click()
        if self._on_dismiss is not None:
            self._on_dismiss()
        dismiss_sheet()

    def _activate_index(self, visible_idx: int) -> None:
        if not self.content:
            return
        if visible_idx < 0 or visible_idx >= len(self.content):
            return
        source_idx = self.visible_to_source(visible_idx)
        if source_idx < 0 or source_idx >= len(self._entries):
            return
        entry = self._entries[source_idx]
        dismiss_sheet()
        if entry.kind == "add_current":
            if self._on_add_current is not None:
                self._on_add_current(entry.path)
            return
        if not entry.path:
            show_toast("Repo path missing", duration=2.0, kind=FeedbackKind.ERROR)
            return
        self._on_switch(entry.path)

    def _handle_mouse_list(self, event: MouseEvent) -> bool:
        """Select on click; double-click activates (viewport_hit timing)."""
        row0 = event.row - 1
        if row0 < 0 or row0 >= self.visible_row_count:
            return False
        content_index = self._r_start + row0
        if content_index >= len(self.content):
            return False
        item_index = content_index
        if self._item_starts is not None:
            item_index, _sub = self.row_to_item(content_index)
        if item_index in self._skip_indices:
            return False
        now = time.monotonic()
        is_double = (
            item_index == self._last_click_index
            and now - self._last_click_time <= DOUBLE_CLICK_MS / 1000.0
        )
        self._last_click_index = item_index
        self._last_click_time = now
        self._select_row(item_index)
        if is_double:
            self._clear_double_click()
            self._activate_index(item_index)
        return True

    def _clear_double_click(self) -> None:
        self._last_click_index = None
        self._last_click_time = 0.0
