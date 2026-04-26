# -*- coding: utf-8 -*-
"""
Module: pigit/app_commit.py
Description: CommitPanel v3 with list view, relative time, and unpushed markers.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

import time
from typing import Callable, Optional, TYPE_CHECKING

from pigit.termui import (
    bind_keys,
    Component,
    LazyLoadMixin,
    ItemSelector,
    keys,
)
from pigit.termui.types import ActionLiteral
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth
from pigit.termui._surface import _DEFAULT_BG

from .app_theme import THEME
from .app_contribution_graph import ContributionGraph

if TYPE_CHECKING:
    from .git.model import Commit


def _relative_time(unix_ts: int) -> str:
    """Return a human-readable relative time string."""
    delta = int(time.time()) - unix_ts
    if delta < 60:
        return f"{delta}s ago"
    if delta < 3600:
        return f"{delta // 60}m ago"
    if delta < 86400:
        return f"{delta // 3600}h ago"
    if delta < 604800:
        return f"{delta // 86400}d ago"
    return f"{delta // 604800}w ago"


class CommitPanel(LazyLoadMixin, ItemSelector):
    """Commit panel with list view, relative time, and unpushed markers."""

    CURSOR = "\u25cf"

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        content: Optional[list[str]] = None,
        *,
        display: Optional[Component] = None,
        on_selection_changed: Optional[Callable] = None,
    ) -> None:
        super().__init__(x, y, size, content, on_selection_changed=on_selection_changed)
        from .git.repo import Repo

        _repo = Repo()
        self.repo_path, self.repo_conf = _repo.confirm_repo()
        self.git = _repo.bind_path(self.repo_path)
        self.commits: list[Commit] = []
        self._view_mode: str = "list"
        self._contrib_graph = ContributionGraph()
        self._display = display

    @bind_keys("j", keys.KEY_DOWN)
    def next(self, step: int = 1) -> None:
        super().next(step)

    @bind_keys("k", keys.KEY_UP)
    def previous(self, step: int = 1) -> None:
        super().previous(step)

    @bind_keys("g")
    def toggle_view(self) -> None:
        """Toggle between list and contribution graph view."""
        if self._view_mode == "list":
            self._view_mode = "river"
        else:
            self._view_mode = "list"

    def get_help_entries(self) -> list[tuple[str, str]]:
        """Return help pairs for commit panel."""
        return [
            ("j/k", "Navigate"),
            ("Enter", "View"),
            ("g", "Toggle view"),
        ]

    def fresh(self) -> None:
        branch_name = self.git.get_head() or ""
        self.commits = commits = self.git.load_commits(branch_name)
        self._contrib_graph.set_commits(commits)
        if not commits:
            self.set_content(["No commits found."])
            self._max_meta_w = 0
            return
        lines = []
        max_meta_w = 0
        for commit in commits:
            lines.append(self._format_commit(commit))
            meta = f"  {commit.author}  {_relative_time(commit.unix_timestamp)}"
            max_meta_w = max(max_meta_w, wcswidth(meta))
        self.set_content(lines)
        self._max_meta_w = max_meta_w

    def _format_commit(self, commit: "Commit") -> str:
        """Format a commit for display."""
        msg = commit.msg
        sha = commit.sha[:7]
        rel = _relative_time(commit.unix_timestamp)
        author = commit.author
        # Build a single-line summary for default content
        marker = "\u25cf" if not commit.is_pushed() else " "
        tag_str = f" {commit.tag[0]}" if commit.tag else ""
        return f"{marker} {sha} {msg}{tag_str}  {author}  {rel}"

    def _render_surface(self, surface) -> None:
        if not self.content:
            return

        if self._view_mode == "river":
            # Render list underneath, then overlay heatmap on top half.
            self._render_list_view(surface)
            self._render_heatmap_overlay(surface)
            return

        self._render_list_view(surface)

    def _render_list_view(self, surface) -> None:
        """Render commit list."""
        w = surface.width
        end = min(self._r_start + self._size[1], len(self.content))
        max_meta_w = getattr(self, "_max_meta_w", 0)

        for idx in range(self._r_start, end):
            row = idx - self._r_start
            is_cursor = idx == self.curr_no

            if idx >= len(self.commits):
                prefix = "\u25cf " if is_cursor else "  "
                text = prefix + self.content[idx]
                if wcswidth(text) > w:
                    text = truncate_by_width(text, w - 1) + "\u2026"
                surface.draw_text_rgb(
                    row, 0, text, fg=THEME.fg_muted, bg=_DEFAULT_BG, bold=is_cursor
                )
                continue

            commit = self.commits[idx]
            x = 0

            # Cursor indicator (reserve 2 cols for alignment)
            if is_cursor:
                surface.draw_text_rgb(
                    row, x, "\u25cf", fg=THEME.fg_primary, bg=_DEFAULT_BG, bold=True
                )
            x += 2

            # Unpushed marker
            if not commit.is_pushed():
                marker = "\u25cf"
                surface.draw_text_rgb(
                    row,
                    x,
                    marker,
                    fg=THEME.accent_yellow,
                    bg=_DEFAULT_BG,
                    bold=is_cursor,
                )
                x += wcswidth(marker) + 1
            else:
                x += 2

            # Draw SHA
            sha = commit.sha[:7]
            surface.draw_text_rgb(
                row, x, sha, fg=THEME.fg_dim, bg=_DEFAULT_BG, bold=is_cursor
            )
            x += len(sha) + 1

            # Draw message (truncated to leave room for meta)
            msg = commit.msg
            author = commit.author
            rel = _relative_time(commit.unix_timestamp)
            meta = f"  {author}  {rel}"
            meta_w = wcswidth(meta)
            tag_str = f" {commit.tag[0]}" if commit.tag else ""
            tag_w = wcswidth(tag_str)

            # Use max meta width across all commits so tail info aligns vertically
            reserve_meta_w = max(max_meta_w, meta_w)
            avail = w - x - reserve_meta_w - tag_w - 1
            if avail > 0:
                if wcswidth(msg) > avail:
                    msg = truncate_by_width(msg, avail - 1) + "\u2026"
                surface.draw_text_rgb(
                    row, x, msg, fg=THEME.fg_primary, bg=_DEFAULT_BG, bold=is_cursor
                )
                x += wcswidth(msg)

            # Draw tag
            if tag_str:
                x += 1
                surface.draw_text_rgb(
                    row,
                    x,
                    tag_str,
                    fg=THEME.accent_cyan,
                    bg=_DEFAULT_BG,
                    bold=is_cursor,
                )
                x += tag_w

            # Draw meta right-aligned using reserved width for vertical alignment.
            # Pad shorter meta with leading spaces so all rows end at the same column.
            meta_x = w - reserve_meta_w
            if meta_x >= 0:
                pad = reserve_meta_w - meta_w
                padded_meta = (" " * pad) + meta if pad > 0 else meta
                surface.draw_text_rgb(
                    row,
                    meta_x,
                    padded_meta,
                    fg=THEME.fg_muted,
                    bg=_DEFAULT_BG,
                    bold=is_cursor,
                )

    def _render_heatmap_overlay(self, surface) -> None:
        """Render contribution heatmap overlay on top of panel."""
        w = surface.width
        h = surface.height
        if w <= 0 or h <= 0:
            return

        graph_h = min(self._contrib_graph.min_height(), h)
        self._contrib_graph.resize((w, graph_h))
        self._contrib_graph._render_surface(surface)

    def on_key(self, key: str) -> None:
        if self._view_mode == "river":
            # Contribution graph is view-only; g toggles back to list.
            return

        if key == keys.KEY_ENTER:
            if not self.commits:
                return
            commit = self.commits[self.curr_no]
            content = self.git.load_commit_info(commit.sha, plain=True).split("\n")
            self.emit(
                ActionLiteral.goto,
                target=self._display,
                source=self,
                content=content,
            )
