# -*- coding: utf-8 -*-
"""
Module: pigit/app_commit.py
Description: CommitPanel v3 with list view, relative time, and inline merge graph.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Callable, Optional, TYPE_CHECKING

from pigit.ext.utils import copy_to_clipboard, relative_time
from pigit.termui import (
    ActionEventType,
    bind_keys,
    Component,
    ItemSelector,
    keys,
    palette,
    Segment,
    show_toast,
)
from pigit.termui.wcwidth_table import wcswidth

from .app_commit_graph import GraphRow, compute_graph_rows
from .app_inspector import CommitInfo
from .app_theme import THEME
from .app_contribution_graph import ContributionGraph


def _parse_decoration(
    extra_info: str, remotes: tuple[str, ...]
) -> tuple[str, list[str], list[str]]:
    """Split git's ``%d`` decoration into ``(head_ref, locals, remotes)``.

    ``%d`` packs HEAD, branches, remote-tracking refs, and tags into one
    parenthesized comma-separated list — the only structural cue between
    them is text prefix. ``head_ref`` is the local branch HEAD points to,
    ``"HEAD"`` for a detached HEAD entry, or ``""`` if HEAD is absent. The
    branch HEAD points at is *not* repeated in ``locals`` so the renderer
    can emit it as part of the HEAD badge without de-duping. Tag entries
    are skipped — they are surfaced via :attr:`Commit.tag` already.
    """
    s = extra_info.strip()
    if not (s.startswith("(") and s.endswith(")")):
        return "", [], []
    body = s[1:-1].strip()
    if not body:
        return "", [], []

    head_ref = ""
    local_refs: list[str] = []
    remote_refs: list[str] = []

    for raw in body.split(","):
        entry = raw.strip()
        if not entry:
            continue
        if entry.startswith("HEAD -> "):
            head_ref = entry.removeprefix("HEAD -> ").strip()
        elif entry == "HEAD":
            head_ref = "HEAD"
        elif entry.startswith("tag: "):
            continue
        elif any(entry.startswith(r + "/") for r in remotes):
            remote_refs.append(entry)
        else:
            local_refs.append(entry)

    return head_ref, local_refs, remote_refs


class CommitViewMode(Enum):
    LIST = auto()
    HEATMAP = auto()


if TYPE_CHECKING:
    from .git.local_git import LocalGit
    from .git.model import Commit


class CommitPanel(ItemSelector):
    """Commit panel with list view, relative time, and inline merge graph."""

    CURSOR = "●"
    GRAPH_COMMIT = "◉"
    GRAPH_VERTICAL = "│"
    GRAPH_OPEN = "╮"
    GRAPH_CLOSE = "╯"
    LANE_PALETTE: tuple[tuple[int, int, int], ...] = (
        THEME.accent_cyan,
        THEME.accent_green,
        THEME.accent_purple,
        THEME.accent_blue,
        THEME.accent_red,
    )

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
        self._graph_rows: list[GraphRow] = []
        self._remotes: tuple[str, ...] = ()
        self._refs_cache: dict[str, tuple[str, list[str], list[str]]] = {}

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

    @bind_keys("y")
    def copy_sha(self) -> None:
        """Copy the selected commit SHA to the clipboard."""
        if not self.commits:
            return
        commit = self.commits[self.curr_no]
        if copy_to_clipboard(commit.sha):
            show_toast(f"Copied {commit.sha[:7]}", duration=1.5)
        else:
            show_toast("Failed to copy to clipboard", duration=2.0)

    def get_help_entries(self) -> list[tuple[str, str]]:
        """Return help pairs for commit panel."""
        return [
            ("j/k", "Navigate"),
            ("Enter", "View"),
            ("g", "Toggle view"),
            ("y", "Copy SHA"),
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
        self._remotes = tuple(self.git.get_remotes())
        self._refs_cache.clear()
        if not commits:
            self.set_content(["No commits found."])
            self._max_meta_w = 0
            self._graph_rows = []
            return
        self._graph_rows = compute_graph_rows(commits)
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
        # Plain-text fallback used during lazy load; rich rendering goes via describe_row.
        tag_str = f" {commit.tag[0]}" if commit.tag else ""
        return f"{sha} {msg}{tag_str}  {author}  {rel}"

    def _render_surface(self, surface) -> None:
        if not self.content:
            return
        super()._render_surface(surface)
        if self._view_mode is CommitViewMode.HEATMAP:
            self._render_heatmap_overlay(surface)

    def describe_row(self, idx: int, is_cursor: bool) -> tuple[
        list[Segment],
        list[Segment] | None,
        list[Segment],
    ]:
        """Return row description: [cursor][graph rails][SHA][msg][tag][meta]"""
        focused = self.is_focus_leaf
        cursor_flags = palette.STYLE_BOLD if is_cursor else 0
        if idx >= len(self.commits):
            prefix = self.CURSOR + " " if is_cursor else "  "
            return (
                [
                    Segment(
                        prefix + self.content[idx],
                        fg=THEME.fg_muted,
                        style_flags=cursor_flags,
                    )
                ],
                None,
                [],
            )

        commit = self.commits[idx]

        # Cursor indicator (2 cols)
        if is_cursor:
            left = [
                Segment(
                    self.CURSOR, fg=THEME.fg_primary, style_flags=palette.STYLE_BOLD
                ),
                Segment(" ", fg=THEME.fg_primary),
            ]
        else:
            left = [Segment("  ", fg=THEME.fg_primary)]

        # Graph rails (2 cols per lane)
        if idx < len(self._graph_rows):
            left.extend(
                self._render_rails(
                    self._graph_rows[idx],
                    commit,
                    cursor_flags=cursor_flags,
                    focused=focused,
                )
            )

        # SHA + spacer (8 cols)
        left.append(Segment(commit.sha[:7], fg=THEME.fg_dim, style_flags=cursor_flags))
        left.append(Segment(" ", fg=THEME.fg_dim if not focused else THEME.fg_primary))

        fg_msg = THEME.fg_primary if focused else THEME.fg_dim
        main: list[Segment] = self._ref_segments(
            commit, focused=focused, cursor_flags=cursor_flags
        )
        main.append(Segment(commit.msg, fg=fg_msg, style_flags=cursor_flags))

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
        fg_meta = THEME.fg_muted if focused else THEME.fg_dim
        right = [Segment(meta, fg=fg_meta, style_flags=cursor_flags)]

        return left, main, right

    def _ref_segments(
        self,
        commit: "Commit",
        *,
        focused: bool,
        cursor_flags: int,
    ) -> list[Segment]:
        """Render branch-ref badges wrapped in orange parens, comma-separated."""
        cached = self._refs_cache.get(commit.sha)
        if cached is None:
            cached = _parse_decoration(commit.extra_info, self._remotes)
            self._refs_cache[commit.sha] = cached
        head_ref, local_refs, remote_refs = cached
        if not (head_ref or local_refs or remote_refs or commit.tag):
            return []

        paren_fg = THEME.accent_orange if focused else THEME.fg_dim
        head_fg = THEME.accent_blue if focused else THEME.fg_dim
        local_fg = THEME.accent_green if focused else THEME.fg_dim
        remote_fg = THEME.accent_magenta if focused else THEME.fg_dim
        tag_fg = THEME.accent_cyan if focused else THEME.fg_dim
        arrow_fg = THEME.fg_primary

        entries: list[list[Segment]] = []
        if head_ref == "HEAD":
            entries.append([Segment("HEAD", fg=head_fg, style_flags=cursor_flags)])
        elif head_ref:
            entries.append(
                [
                    Segment("HEAD", fg=head_fg, style_flags=cursor_flags),
                    Segment("->", fg=arrow_fg, style_flags=cursor_flags),
                    Segment(head_ref, fg=local_fg, style_flags=cursor_flags),
                ]
            )
        for name in local_refs:
            entries.append([Segment(name, fg=local_fg, style_flags=cursor_flags)])
        for name in remote_refs:
            entries.append([Segment(name, fg=remote_fg, style_flags=cursor_flags)])
        if commit.tag:
            entries.append(
                [Segment(commit.tag[0], fg=tag_fg, style_flags=cursor_flags)]
            )

        segs: list[Segment] = [Segment("(", fg=paren_fg, style_flags=cursor_flags)]
        for i, entry in enumerate(entries):
            if i > 0:
                segs.append(Segment(", ", fg=paren_fg, style_flags=cursor_flags))
            segs.extend(entry)
        segs.append(Segment(") ", fg=paren_fg, style_flags=cursor_flags))
        return segs

    def _render_rails(
        self,
        row: GraphRow,
        commit: "Commit",
        *,
        cursor_flags: int,
        focused: bool,
    ) -> list[Segment]:
        """Render graph rails for one row.

        Layout per lane: [rail char][space], 2 columns wide. All active lanes
        are rendered; if total width pushes the message column too narrow, the
        renderer truncates the message segment instead of the rails.
        """
        total_lanes = max(len(row.lanes_before), len(row.lanes_after))
        segments: list[Segment] = []
        for i in range(total_lanes):
            ch, fg = self._lane_glyph(row, i, commit, focused=focused)
            segments.append(Segment(ch + " ", fg=fg, style_flags=cursor_flags))
        return segments

    def _lane_glyph(
        self,
        row: GraphRow,
        i: int,
        commit: "Commit",
        *,
        focused: bool,
    ) -> tuple[str, tuple[int, int, int]]:
        """Pick the glyph and color for lane ``i`` on this row."""
        lane_color = self.LANE_PALETTE[i % len(self.LANE_PALETTE)]
        lane_fg = lane_color if focused else THEME.fg_dim

        if i == row.commit_lane:
            commit_color = THEME.accent_yellow if not commit.is_pushed() else lane_color
            return self.GRAPH_COMMIT, commit_color

        if i in row.closed_lanes:
            return self.GRAPH_CLOSE, lane_fg

        if i in row.opened_lanes:
            return self.GRAPH_OPEN, lane_fg

        before_active = i < len(row.lanes_before) and row.lanes_before[i] is not None
        after_active = i < len(row.lanes_after) and row.lanes_after[i] is not None
        if before_active or after_active:
            return self.GRAPH_VERTICAL, lane_fg

        return " ", THEME.fg_dim

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
