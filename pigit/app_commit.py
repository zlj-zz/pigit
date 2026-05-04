# -*- coding: utf-8 -*-
"""
Module: pigit/app_commit.py
Description: CommitPanel v3 with list view, relative time, and inline merge graph.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

import datetime
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

if TYPE_CHECKING:
    from .git.local_git import LocalGit
    from .git.model import Commit


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


class _SubRow(Enum):
    """Per-commit sub-row kinds emitted in expanded mode."""

    COMMIT = auto()  # SHA + refs + subject
    MERGE = auto()  # ``Merge: p1[:7] p2[:7] ...`` (only for merges)
    AUTHOR = auto()  # ``Author: <name>``
    DATE = auto()  # ``Date:   <localized abs time>``
    BLANK = auto()  # blank separator before message body
    MESSAGE = auto()  # one body line; payload is line index
    TAIL = auto()  # blank trailer between commits


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
        self._abs_time_cache: dict[str, str] = {}
        self._max_meta_w = 0
        self._graph_rows: list[GraphRow] = []
        self._remotes: tuple[str, ...] = ()
        self._refs_cache: dict[str, tuple[str, list[str], list[str]]] = {}
        self._expanded = False
        self._bodies: Optional[dict[str, str]] = None
        self._body_lines_cache: dict[str, list[str]] = {}

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

    @bind_keys("z")
    def toggle_expanded(self) -> None:
        """Toggle compact (single-line) and expanded (git-log style) commit rows."""
        if self._view_mode is not CommitViewMode.LIST:
            return
        self._expanded = not self._expanded
        if self._expanded:
            self._ensure_bodies()
        saved_idx = self.curr_no
        self._rebuild_rows()
        if self.commits:
            self.curr_no = max(0, min(saved_idx, len(self.commits) - 1))
            self._scroll_into_view()

    def get_help_title(self) -> str:
        return "Commit"

    @bind_keys("y")
    def copy_sha(self) -> None:
        """Copy the selected commit SHA to the clipboard."""
        commit = self._current_commit()
        if commit is None:
            return
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
            ("z", "Toggle expanded"),
            ("y", "Copy SHA"),
        ]

    def _current_commit(self) -> Optional["Commit"]:
        """Return the commit at ``curr_no`` (item index in either mode)."""
        if not self.commits:
            return None
        if 0 <= self.curr_no < len(self.commits):
            return self.commits[self.curr_no]
        return None

    def get_inspector_data(self) -> Optional[CommitInfo]:
        """Return inspector data for the currently selected commit."""
        c = self._current_commit()
        if c is None:
            return None
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
        self._bodies = None
        self._body_lines_cache.clear()
        if not commits:
            self.set_content(["No commits found."])
            self._max_meta_w = 0
            self._graph_rows = []
            return
        self._graph_rows = compute_graph_rows(commits)
        self._rel_time_cache.clear()
        self._abs_time_cache.clear()
        for commit in commits:
            self._rel_time_cache[commit.sha] = relative_time(commit.unix_timestamp)
            self._abs_time_cache[commit.sha] = self._format_abs_time(
                commit.unix_timestamp
            )
        if self._expanded:
            self._ensure_bodies()
        self._rebuild_rows()

    def _ensure_bodies(self) -> None:
        if self._bodies is not None or not self.commits:
            return
        branch_name = self.git.get_head() or ""
        self._bodies = self.git.get_commit_bodies(branch_name)
        self._body_lines_cache.clear()

    def _body_lines(self, commit: "Commit") -> list[str]:
        """Return body lines for ``commit`` (subject excluded), cached per-sha."""
        cached = self._body_lines_cache.get(commit.sha)
        if cached is not None:
            return cached
        body = (self._bodies or {}).get(commit.sha, "")
        # ``%B`` packs ``Subject\n\nBody...`` so we drop everything up to the
        # first blank line; the subject already lives on the COMMIT row.
        parts = body.split("\n\n", 1)
        if len(parts) < 2 or not parts[1].strip():
            lines: list[str] = []
        else:
            lines = parts[1].rstrip("\n").split("\n")
        self._body_lines_cache[commit.sha] = lines
        return lines

    @staticmethod
    def _format_abs_time(unix_ts: int) -> str:
        """``Wed May 04 12:34:56 2026 +0800`` — local time, git-log compatible."""
        dt = datetime.datetime.fromtimestamp(unix_ts).astimezone()
        return dt.strftime("%a %b %d %H:%M:%S %Y %z")

    def _rebuild_rows(self) -> None:
        """Rebuild ``content`` (and ``item_starts`` if expanded) from ``commits``."""
        if not self.commits:
            return
        if self._expanded:
            lines, starts = self._build_expanded()
            self.set_content(lines)
            self.set_item_starts(starts)
        else:
            lines, max_meta_w = self._build_compact()
            self.set_content(lines)
            self._max_meta_w = max_meta_w

    def _build_compact(self) -> tuple[list[str], int]:
        """One row per commit; return ``(lines, max_meta_width)``."""
        lines: list[str] = []
        max_meta_w = 0
        for commit in self.commits:
            rel = self._rel_time_cache.get(commit.sha) or relative_time(
                commit.unix_timestamp
            )
            lines.append(self._format_compact(commit))
            meta = f"  {commit.author}  {rel}"
            max_meta_w = max(max_meta_w, wcswidth(meta))
        return lines, max_meta_w

    def _build_expanded(self) -> tuple[list[str], list[int]]:
        """Multi-row layout per commit; return ``(lines, item_starts)``.

        ``lines`` are placeholder empty strings — ``describe_row`` produces the
        rich rendering. The framework only needs ``len(lines)`` for row bounds.
        """
        lines: list[str] = []
        starts: list[int] = []
        for commit in self.commits:
            starts.append(len(lines))
            lines.extend([""] * len(self._schema_for(commit)))
        return lines, starts

    def _schema_for(self, commit: "Commit") -> list[tuple[_SubRow, int]]:
        """Pure function of ``(commit.is_merge, len(body_lines))``.

        Cheap to recompute since ``_body_lines`` is cached; returning a fresh
        list each call avoids storing per-commit schema state.
        """
        body_lines = self._body_lines(commit)
        schema: list[tuple[_SubRow, int]] = [(_SubRow.COMMIT, 0)]
        if commit.is_merge:
            schema.append((_SubRow.MERGE, 0))
        schema.append((_SubRow.AUTHOR, 0))
        schema.append((_SubRow.DATE, 0))
        if body_lines:
            schema.append((_SubRow.BLANK, 0))
            for i in range(len(body_lines)):
                schema.append((_SubRow.MESSAGE, i))
        schema.append((_SubRow.TAIL, 0))
        return schema

    def _format_compact(self, commit: "Commit") -> str:
        """Plain-text used for ``set_content`` width measurements; rich
        rendering is produced by ``describe_row``."""
        msg = commit.msg
        sha = commit.sha[:7]
        rel = self._rel_time_cache.get(commit.sha) or relative_time(
            commit.unix_timestamp
        )
        author = commit.author
        tag_str = f" {commit.tag[0]}" if commit.tag else ""
        return f"{sha} {msg}{tag_str}  {author}  {rel}"

    def _render_surface(self, surface) -> None:
        if not self.content:
            return
        super()._render_surface(surface)
        if self._view_mode is CommitViewMode.HEATMAP:
            self._render_heatmap_overlay(surface)

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: Optional[int] = None,
        sub_row: int = 0,
    ) -> tuple[
        list[Segment],
        list[Segment] | None,
        list[Segment],
    ]:
        """Return row description.

        Compact mode: ``[cursor][graph rails][SHA][refs][msg][meta]``.
        Expanded mode dispatches to per-sub-row helpers.
        """
        focused = self.is_focus_leaf

        # Placeholder ("No commits found.") — the only case where content
        # outranks commits.
        if not self.commits:
            cursor_flags = palette.STYLE_BOLD if is_cursor else 0
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

        if item_idx is None:
            return self._describe_compact(self.commits[idx], idx, is_cursor, focused)

        commit = self.commits[item_idx]
        kind, payload = self._schema_for(commit)[sub_row]
        if kind is _SubRow.COMMIT:
            left, main = self._commit_left_main(commit, item_idx, is_cursor, focused)
            return left, main, []
        return self._describe_sub_row(commit, item_idx, kind, payload, focused)

    def _describe_compact(
        self,
        commit: "Commit",
        item_idx: int,
        is_cursor: bool,
        focused: bool,
    ) -> tuple[list[Segment], list[Segment], list[Segment]]:
        cursor_flags = palette.STYLE_BOLD if is_cursor else 0
        left, main = self._commit_left_main(commit, item_idx, is_cursor, focused)
        author = commit.author
        rel = self._rel_time_cache.get(commit.sha) or relative_time(
            commit.unix_timestamp
        )
        meta = f"  {author}  {rel}"
        meta_w = wcswidth(meta)
        reserve = max(self._max_meta_w, meta_w)
        if reserve > meta_w:
            meta = " " * (reserve - meta_w) + meta
        fg_meta = THEME.fg_muted if focused else THEME.fg_dim
        right = [Segment(meta, fg=fg_meta, style_flags=cursor_flags)]
        return left, main, right

    def _commit_left_main(
        self,
        commit: "Commit",
        item_idx: int,
        is_cursor: bool,
        focused: bool,
    ) -> tuple[list[Segment], list[Segment]]:
        """Build the cursor + rails + sha + refs + subject portion of a COMMIT row."""
        cursor_flags = palette.STYLE_BOLD if is_cursor else 0
        if is_cursor:
            left: list[Segment] = [
                Segment(self.CURSOR, fg=THEME.fg_primary, style_flags=cursor_flags),
                Segment(" ", fg=THEME.fg_primary),
            ]
        else:
            left = [Segment("  ", fg=THEME.fg_primary)]

        if item_idx < len(self._graph_rows):
            left.extend(
                self._render_rails(
                    self._graph_rows[item_idx],
                    commit,
                    cursor_flags=cursor_flags,
                    focused=focused,
                )
            )

        left.append(Segment(commit.sha[:7], fg=THEME.fg_dim, style_flags=cursor_flags))
        left.append(Segment(" ", fg=THEME.fg_dim if not focused else THEME.fg_primary))

        fg_msg = THEME.fg_primary if focused else THEME.fg_dim
        main: list[Segment] = self._ref_segments(
            commit, focused=focused, cursor_flags=cursor_flags
        )
        main.append(Segment(commit.msg, fg=fg_msg, style_flags=cursor_flags))
        return left, main

    def _describe_sub_row(
        self,
        commit: "Commit",
        item_idx: int,
        kind: _SubRow,
        payload: int,
        focused: bool,
    ) -> tuple[list[Segment], list[Segment], list[Segment]]:
        """Render a non-COMMIT sub-row (Merge:/Author:/Date:/blank/body line).

        The cursor only ever lives on a COMMIT row, so sub-rows are never
        styled bold and we omit ``cursor_flags`` entirely.
        """
        left: list[Segment] = [Segment("  ", fg=THEME.fg_primary)]
        if item_idx < len(self._graph_rows):
            left.extend(
                self._render_rails(
                    self._graph_rows[item_idx],
                    None,
                    sub=True,
                    cursor_flags=0,
                    focused=focused,
                )
            )

        if kind in (_SubRow.BLANK, _SubRow.TAIL):
            return left, [], []

        fg_label = THEME.fg_muted if focused else THEME.fg_dim
        fg_value = THEME.fg_primary if focused else THEME.fg_dim
        if kind is _SubRow.MERGE:
            text = " ".join(p[:7] for p in commit.parents)
            main = [
                Segment("Merge: ", fg=fg_label),
                Segment(text, fg=fg_value),
            ]
        elif kind is _SubRow.AUTHOR:
            main = [
                Segment("Author: ", fg=fg_label),
                Segment(commit.author, fg=fg_value),
            ]
        elif kind is _SubRow.DATE:
            text = self._abs_time_cache.get(commit.sha) or self._format_abs_time(
                commit.unix_timestamp
            )
            main = [
                Segment("Date:   ", fg=fg_label),
                Segment(text, fg=fg_value),
            ]
        elif kind is _SubRow.MESSAGE:
            body_lines = self._body_lines(commit)
            text = body_lines[payload] if 0 <= payload < len(body_lines) else ""
            main = [
                Segment("    ", fg=fg_value),
                Segment(text, fg=fg_value),
            ]
        else:
            main = []
        return left, main, []

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
        commit: Optional["Commit"],
        *,
        sub: bool = False,
        cursor_flags: int,
        focused: bool,
    ) -> list[Segment]:
        """Render graph rails for one row (2 columns per lane).

        ``sub=True`` is used for non-commit rows below a COMMIT row: only
        active ``lanes_after`` get a vertical pipe, and curve / commit glyphs
        are skipped (they belong to the commit row only). ``commit`` may be
        ``None`` in this mode.
        """
        if sub:
            segments: list[Segment] = []
            for i, sha in enumerate(row.lanes_after):
                if sha is None:
                    segments.append(
                        Segment("  ", fg=THEME.fg_dim, style_flags=cursor_flags)
                    )
                    continue
                color = self.LANE_PALETTE[i % len(self.LANE_PALETTE)]
                fg = color if focused else THEME.fg_dim
                segments.append(
                    Segment(self.GRAPH_VERTICAL + " ", fg=fg, style_flags=cursor_flags)
                )
            return segments

        total_lanes = max(len(row.lanes_before), len(row.lanes_after))
        segments = []
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
