# -*- coding: utf-8 -*-
"""
Module: pigit/app_inspector.py
Description: Right-side inspector panel for file/branch/commit details.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from pigit.ext.utils import relative_time
from pigit.termui import Component, palette
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth

from .app_theme import THEME

if TYPE_CHECKING:
    from .git.model import Branch, Commit, File


class InspectorPanel(Component):
    """Right-side panel showing file/branch/commit details."""

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size)
        self._content: list[str] = []
        self._title = "Inspector"

    def clear(self) -> None:
        """Clear inspector content."""
        self._content = []
        self._title = "Inspector"

    def show_file(
        self,
        file: "File",
        size: str = "?",
        mtime: str = "?",
    ) -> None:
        """Display file details."""
        self._title = "File"
        status = []
        if file.has_staged_change:
            status.append("staged")
        if file.has_unstaged_change:
            status.append("unstaged")
        if file.deleted:
            status.append("deleted")
        if not file.tracked:
            status.append("untracked")
        if file.has_merged_conflicts:
            status.append("conflict")

        self._content = [
            file.name,
            "─" * 20,
            f"Status: {', '.join(status) if status else 'clean'}",
            f"Size: {size}",
            f"Modified: {mtime}",
            f"Tracked: {'yes' if file.tracked else 'no'}",
        ]

    def show_branch(
        self,
        branch: "Branch",
        recent_msg: str = "?",
        recent_author: str = "?",
        created: str = "?",
    ) -> None:
        """Display branch details."""
        self._title = "Branch"
        upstream = branch.upstream_name or "none"
        ahead = branch.ahead if branch.ahead != "?" else "0"
        behind = branch.behind if branch.behind != "?" else "0"

        self._content = [
            branch.name,
            "─" * 20,
            f"Current: {'yes' if branch.is_head else 'no'}",
            f"Upstream: {upstream}",
            f"Ahead: {ahead}",
            f"Behind: {behind}",
        ]
        if recent_msg != "?":
            self._content.append(f"Recent: {recent_msg}")
        if recent_author != "?":
            self._content.append(f"By: {recent_author}")
        if created != "?":
            self._content.append(f"Created: {created}")

    def show_commit(
        self,
        commit: "Commit",
        changed_files: Optional[list[tuple[str, int, int]]] = None,
        total_add: int = 0,
        total_del: int = 0,
    ) -> None:
        """Display commit details."""
        self._title = "Commit"
        tags = ", ".join(commit.tag) if commit.tag else "none"
        rel_time = relative_time(commit.unix_timestamp)

        self._content = [
            commit.sha[:7],
            "─" * 20,
            commit.msg,
            f"Author: {commit.author}",
            f"Time: {rel_time}",
            f"Status: {commit.status}",
            f"Tags: {tags}",
        ]
        if total_add or total_del:
            self._content.append(f"Changes: +{total_add} -{total_del}")
        if changed_files:
            self._content.append("─" * 20)
            self._content.append("Files:")
            for file_name, add, delete in changed_files[:8]:
                self._content.append(f"  {file_name} +{add} -{delete}")
            if len(changed_files) > 8:
                self._content.append(f"  ... and {len(changed_files) - 8} more")

    def _render_surface(self, surface) -> None:
        w = surface.width
        h = surface.height
        if w <= 0 or h <= 0:
            return

        # Left border and separator
        content_x = 2
        surface.draw_vline_rgb(0, 0, h, fg=THEME.fg_dim, bg=palette.DEFAULT_BG)
        if h > 1:
            surface.draw_hline_rgb(
                1, content_x, w - content_x, fg=THEME.fg_dim, bg=palette.DEFAULT_BG
            )

        # Title
        title = f" {self._title} "
        title_w = wcswidth(title)
        if title_w < w - content_x:
            surface.draw_text_rgb(
                0,
                content_x,
                title,
                fg=THEME.accent_cyan,
                bg=palette.DEFAULT_BG,
                bold=True,
            )

        # Content lines
        for i, line in enumerate(self._content):
            row = i + 2
            if row >= h:
                break
            text = line
            avail = w - content_x
            if wcswidth(text) > avail:
                text = truncate_by_width(text, avail - 1) + "…"
            surface.draw_text_rgb(
                row, content_x, text, fg=THEME.fg_primary, bg=palette.DEFAULT_BG
            )
