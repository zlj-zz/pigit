# -*- coding: utf-8 -*-
"""
Module: pigit/app_inspector.py
Description: Right-side inspector panel for file/branch/commit details.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING, Union

from pigit.ext.utils import relative_time
from pigit.termui import Component, palette
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth

from .app_theme import THEME

if TYPE_CHECKING:
    from .git.model import Branch, Commit, File


@dataclass
class FileInfo:
    file: "File"
    size: str
    mtime: str


@dataclass
class BranchInfo:
    branch: "Branch"
    recent_msg: str
    recent_author: str
    created: str


@dataclass
class CommitInfo:
    commit: "Commit"
    changed_files: list[tuple[str, int, int]]
    total_add: int
    total_del: int


InspectorData = Union[FileInfo, BranchInfo, CommitInfo, None]


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

    def show(self, data: InspectorData) -> None:
        """Display inspector content from a data object."""
        self.clear()
        if data is None:
            return
        if isinstance(data, FileInfo):
            self._show_file_impl(data)
        elif isinstance(data, BranchInfo):
            self._show_branch_impl(data)
        elif isinstance(data, CommitInfo):
            self._show_commit_impl(data)

    def update_from(self, source) -> None:
        """Refresh content from *source* if it provides inspector data.

        Caches by ``(id(source), curr_no)`` to avoid redundant git calls.
        """
        if not hasattr(source, "get_inspector_data"):
            return
        idx = getattr(source, "curr_no", 0)
        key = (id(source), idx)
        if getattr(self, "_last_key", None) == key:
            return
        self._last_key = key
        self.show(source.get_inspector_data())

    def _show_file_impl(self, data: FileInfo) -> None:
        """Display file details."""
        file = data.file
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
            f"Size: {data.size}",
            f"Modified: {data.mtime}",
            f"Tracked: {'yes' if file.tracked else 'no'}",
        ]

    def _show_branch_impl(self, data: BranchInfo) -> None:
        """Display branch details."""
        branch = data.branch
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
        if data.recent_msg != "?":
            self._content.append(f"Recent: {data.recent_msg}")
        if data.recent_author != "?":
            self._content.append(f"By: {data.recent_author}")
        if data.created != "?":
            self._content.append(f"Created: {data.created}")

    def _show_commit_impl(self, data: CommitInfo) -> None:
        """Display commit details."""
        commit = data.commit
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
        if data.total_add or data.total_del:
            self._content.append(f"Changes: +{data.total_add} -{data.total_del}")
        if data.changed_files:
            self._content.append("─" * 20)
            self._content.append("Files:")
            for file_name, add, delete in data.changed_files[:8]:
                self._content.append(f"  {file_name} +{add} -{delete}")
            if len(data.changed_files) > 8:
                self._content.append(f"  ... and {len(data.changed_files) - 8} more")

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
                style_flags=palette.STYLE_BOLD,
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
