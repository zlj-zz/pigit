# -*- coding: utf-8 -*-
"""
Module: pigit/app_commit.py
Description: CommitPanel v3 with list view, relative time, and unpushed markers.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Callable, Optional, TYPE_CHECKING

from pigit.ext.utils import relative_time
from pigit.termui import (
    ActionEventType,
    bind_keys,
    Component,
    ItemSelector,
    keys,
)
from pigit.termui.wcwidth_table import wcswidth

from .app_inspector import CommitInfo
from .app_theme import THEME
from .app_contribution_graph import ContributionGraph


class CommitViewMode(Enum):
    LIST = auto()
    HEATMAP = auto()


if TYPE_CHECKING:
    from .git.local_git import LocalGit
    from .git.model import Commit


class CommitPanel(ItemSelector):
    """Commit panel with list view, relative time, and unpushed markers."""

    CURSOR = "\u25cf"

    def __init__(
        self,
        *,
        display: Optional[Component] = None,
        on_selection_changed: Optional[Callable] = None,
        git: "LocalGit",
    ) -> None:
        super().__init__(
            on_selection_changed=on_selection_changed,
            lazy_load=True,
        )
        self.git = git
        self.commits: list[Commit] = []
        self._view_mode = CommitViewMode.LIST
        self._contrib_graph = ContributionGraph()
        self._display = display
        self._rel_time_cache: dict[str, str] = {}
        self._max_meta_w = 0

    @bind_keys("j", keys.KEY_DOWN)
    def next(self, step: int = 1) -> None:
        super().next(step)

    @bind_keys("k", keys.KEY_UP)
    def previous(self, step: int = 1) -> None:
        super().previous(step)

    @bind_keys("g")
    def toggle_view(self) -> None:
        """Toggle between list and contribution graph view."""
        if self._view_mode is CommitViewMode.LIST:
            self._view_mode = CommitViewMode.HEATMAP
        else:
            self._view_mode = CommitViewMode.LIST

    def get_help_title(self) -> str:
        return "Commit"

    def get_help_entries(self) -> list[tuple[str, str]]:
        """Return help pairs for commit panel."""
        return [
            ("j/k", "Navigate"),
            ("Enter", "View"),
            ("g", "Toggle view"),
        ]

    def get_inspector_data(self) -> Optional[CommitInfo]:
        """Return inspector data for the currently selected commit."""
        idx = self.curr_no
        if not self.commits or not (0 <= idx < len(self.commits)):
            return None
        c = self.commits[idx]
        changed_files, total_add, total_del = [], 0, 0
        if self.git is not None:
            changed_files, total_add, total_del = self.git.get_commit_stats(c.sha)
        return CommitInfo(
            commit=c,
            changed_files=changed_files,
            total_add=total_add,
            total_del=total_del,
        )

    def refresh(self) -> None:
        branch_name = self.git.get_head() or ""
        self.commits = commits = self.git.load_commits(branch_name)
        self._contrib_graph.set_commits(commits)
        if not commits:
            self.set_content(["No commits found."])
            self._max_meta_w = 0
            return
        lines = []
        max_meta_w = 0
        self._rel_time_cache.clear()
        for commit in commits:
            rel = relative_time(commit.unix_timestamp)
            self._rel_time_cache[commit.sha] = rel
            lines.append(self._format_commit(commit))
            meta = f"  {commit.author}  {rel}"
            max_meta_w = max(max_meta_w, wcswidth(meta))
        self.set_content(lines)
        self._max_meta_w = max_meta_w

    def _format_commit(self, commit: "Commit") -> str:
        """Format a commit for display."""
        msg = commit.msg
        sha = commit.sha[:7]
        rel = self._rel_time_cache.get(commit.sha) or relative_time(
            commit.unix_timestamp
        )
        author = commit.author
        # Build a single-line summary for default content
        marker = "\u25cf" if not commit.is_pushed() else " "
        tag_str = f" {commit.tag[0]}" if commit.tag else ""
        return f"{marker} {sha} {msg}{tag_str}  {author}  {rel}"

    def _render_surface(self, surface) -> None:
        if not self.content:
            return
        super()._render_surface(surface)
        if self._view_mode is CommitViewMode.HEATMAP:
            self._render_heatmap_overlay(surface)

    def describe_row(self, idx: int, is_cursor: bool) -> tuple[
        list[tuple[str, tuple[int, int, int], bool]],
        list[tuple[str, tuple[int, int, int], bool]] | None,
        list[tuple[str, tuple[int, int, int], bool]],
    ]:
        """Return row description: [cursor][unpushed][SHA][msg][tag][meta]"""
        if idx >= len(self.commits):
            prefix = "\u25cf " if is_cursor else "  "
            return ([(prefix + self.content[idx], THEME.fg_muted, is_cursor)], None, [])

        commit = self.commits[idx]

        # Cursor indicator (2 cols)
        if is_cursor:
            left = [("\u25cf", THEME.fg_primary, True), (" ", THEME.fg_primary, False)]
        else:
            left = [("  ", THEME.fg_primary, False)]

        # Unpushed marker (2 cols)
        if not commit.is_pushed():
            left.append(("\u25cf", THEME.accent_yellow, is_cursor))
            left.append((" ", THEME.fg_primary, False))
        else:
            left.append(("  ", THEME.fg_primary, False))

        # SHA + spacer (8 cols)
        left.append((commit.sha[:7], THEME.fg_dim, is_cursor))
        left.append((" ", THEME.fg_primary, False))

        # Main: message + optional tag
        tag_str = f" {commit.tag[0]}" if commit.tag else ""
        main = [
            (commit.msg, THEME.fg_primary, is_cursor),
            (tag_str, THEME.accent_cyan, is_cursor),
        ]

        # Right: padded meta
        author = commit.author
        rel = self._rel_time_cache.get(commit.sha) or relative_time(
            commit.unix_timestamp
        )
        meta = f"  {author}  {rel}"
        meta_w = wcswidth(meta)
        max_meta_w = self._max_meta_w
        reserve = max(max_meta_w, meta_w)
        pad = reserve - meta_w
        if pad > 0:
            meta = " " * pad + meta
        right = [(meta, THEME.fg_muted, is_cursor)]

        return left, main, right

    def _render_heatmap_overlay(self, surface) -> None:
        """Render contribution heatmap overlay on top of panel."""
        w = surface.width
        h = surface.height
        if w <= 0 or h <= 0:
            return

        graph_h = min(self._contrib_graph.min_height(), h)
        self._contrib_graph.resize((w, graph_h))
        self._contrib_graph.render_into(surface)

    def on_key(self, key: str) -> None:
        if self._view_mode is CommitViewMode.HEATMAP:
            # Contribution graph is view-only; g toggles back to list.
            return

        if key == keys.KEY_ENTER:
            if not self.commits:
                return
            commit = self.commits[self.curr_no]
            content = self.git.load_commit_info(commit.sha, plain=True).split("\n")
            self.emit(
                ActionEventType.goto,
                target=self._display,
                source=self,
                content=content,
            )
