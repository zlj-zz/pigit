"""
Module: pigit/app_commit.py
Description: CommitPanel v3 with list view, relative time, and inline merge graph.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

import datetime
from enum import Enum, auto
from typing import TYPE_CHECKING
from collections.abc import Callable

from pigit.ext.utils import copy_to_clipboard, relative_time
from pigit.termui import (
    EVT_GOTO,
    EVT_SELECTION_CHANGED,
    EventType,
    FeedbackKind,
    Component,
    Surface,
    bind_action,
    bind_signals,
    dismiss_sheet,
    palette,
    run_async,
    Segment,
    show_badge,
    show_sheet,
    show_toast,
)
from pigit.termui.widgets import OptionList
from pigit.termui.wcwidth_table import wcswidth

from .app_types import CommitSnapshot, GraphRow
from .app_diff import DiffType
from .app_theme import THEME
from .app_contribution_graph import ContributionGraph
from .viewmodels.base import ActionResult
from .viewmodels.commit import ICommitViewModel

if TYPE_CHECKING:
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


class _SubRow(Enum):
    """Per-commit sub-row kinds emitted in expanded mode."""

    COMMIT = auto()  # SHA + refs + subject
    MERGE = auto()  # ``Merge: p1[:7] p2[:7] ...`` (only for merges)
    AUTHOR = auto()  # ``Author: <name>``
    DATE = auto()  # ``Date:   <localized abs time>``
    BLANK = auto()  # blank separator before message body
    MESSAGE = auto()  # one body line; payload is line index
    TAIL = auto()  # blank trailer between commits


class _CommitReportBand(Component):
    """OptionList footer band for the contribution-graph report strip.

    Height is all-or-nothing: ``REPORT_H`` when enabled and the panel is tall
    enough, otherwise 0 so the list keeps the full viewport.
    """

    def __init__(
        self,
        graph: ContributionGraph,
        *,
        report_h: int,
        min_panel_h: int,
        enabled: bool = True,
    ) -> None:
        super().__init__()
        self._graph = graph
        self._report_h = report_h
        self._min_panel_h = min_panel_h
        self.enabled = enabled

    def chrome_band_height(self, width: int, panel_height: int) -> int:
        """Return fitted report height for ``OptionList`` band layout."""
        del width
        if not self.enabled or panel_height <= self._min_panel_h:
            return 0
        return self._report_h

    def paint(self, surface: Surface) -> None:
        self._graph.resize((surface.width, surface.height))
        self._graph.paint(surface)

    def handle_mouse(self, event) -> bool:
        return self._graph.handle_mouse(event)


class CommitPanel(OptionList):
    """Commit panel with list view, relative time, and inline merge graph."""

    CURSOR = "●"
    GRAPH_COMMIT = "◉"
    GRAPH_VERTICAL = "│"
    GRAPH_OPEN = "╮"
    GRAPH_CLOSE = "╯"
    # One column between OptionList cursor mark and graph rails (all row kinds).
    GRAPH_PAD = " "
    REPORT_H = 15  # top pad (2) + content (12) + bottom blank (1)
    REPORT_MIN_HEIGHT = 19

    def __init__(
        self,
        *,
        on_selection_changed: Callable | None = None,
        vm: ICommitViewModel,
        id: str | None = None,
        report_default: bool = True,
    ) -> None:
        self._contrib_graph = ContributionGraph()
        self._report_band = _CommitReportBand(
            self._contrib_graph,
            report_h=self.REPORT_H,
            min_panel_h=self.REPORT_MIN_HEIGHT,
            enabled=report_default,
        )
        super().__init__(
            on_selection_changed=on_selection_changed,
            lazy_load=True,
            id=id,
            on_search_changed=lambda: self._apply_filter(),
            footer=self._report_band,
        )
        self._vm = vm
        self.commits: list[Commit] = []
        self._all_commits: list[Commit] = []
        self._source_map: list[int] = []
        self._report_enabled = report_default
        self._rel_time_cache: dict[str, str] = {}
        self._abs_time_cache: dict[str, str] = {}
        self._max_meta_w = 0
        self._refs_cache: dict[str, tuple[str, list[str], list[str]]] = {}
        self._expanded = False
        self._bodies: dict[str, str] | None = None
        self._body_lines_cache: dict[str, list[str]] = {}
        self._vm_unsubs: list[Callable[[], None]] = []
        # Active (non-stolen) left/main Segments; cursor + steal rebuild live.
        self._row_cache: list[tuple[tuple[Segment, ...], tuple[Segment, ...]]] = []

    keymap_namespace = "commit"
    tab_key = "4"

    @property
    def tab_name(self) -> str:
        """Header tab label; includes the pinned log ref when browsing away from HEAD."""
        return self.get_help_title()

    def _publish_tab_title(self) -> None:
        """Ask the header to reread ``tab_name`` after ``log_ref`` changes."""
        self.emit(EVT_SELECTION_CHANGED)

    @bind_action("next", "j", "down", desc="Navigate commit list", tip="Navigate")
    def next(self, step: int = 1) -> None:
        super().next(step)

    @bind_action("previous", "k", "up", desc="Navigate commit list", tip="Navigate")
    def previous(self, step: int = 1) -> None:
        super().previous(step)

    @bind_action("view_diff", "enter", desc="View commit diff", tip="View")
    def view_diff(self) -> None:
        if not self.commits:
            return
        source_idx = self._source_index(self.curr_no)
        content = self._vm.load_diff(source_idx)
        self.emit(
            EVT_GOTO,
            target="diff",
            source=self,
            key=self.commits[self.curr_no].sha,
            content=content,
            repo_path=self._vm.repo_path,
            diff_type=DiffType.COMMIT,
        )

    @bind_action(
        "cherry_pick",
        "c",
        desc="Cherry-pick onto current HEAD",
        tip="Cherry-pick",
    )
    def cherry_pick(self) -> None:
        """Ask the app to copy the selected commit onto HEAD."""
        commit = self._current_commit()
        if commit is None:
            return
        self.emit(
            EventType("action_requested"),
            cmd="cherry-pick",
            sha=commit.sha,
            is_merge=commit.is_merge,
        )

    @bind_action("open_log_ref", "o", desc="Show log of another ref")
    def open_log_ref(self) -> None:
        """Open a sheet to choose which ref the commit list shows."""
        from .app_log_ref import LogRefSheet

        sheet = LogRefSheet(
            names=self._vm.list_log_ref_names(),
            current_ref=self._vm.log_ref,
            on_pick=self._on_log_ref_picked,
            on_done=dismiss_sheet,
        )
        show_sheet(sheet, max_fraction=0.5, title="Log ref")
        sheet.mount()

    def _on_log_ref_picked(self, name: str) -> None:
        """Apply a ref chosen in the log-ref sheet."""
        self._vm.set_log_ref(name)
        if not self._vm.viewing_checkout_log():
            show_toast(f"Showing log: {name}", duration=1.5, kind=FeedbackKind.INFO)
        self._publish_tab_title()

    @bind_action(
        "toggle_expanded", "z", desc="Toggle expanded commit details", tip="Expand"
    )
    def toggle_expanded(self) -> None:
        """Toggle compact (single-line) and expanded (git-log style) commit rows."""
        self._expanded = not self._expanded
        if self._expanded:
            self._ensure_bodies()
        saved_idx = self.curr_no
        self._rebuild_rows()
        if self.commits:
            self.curr_no = max(0, min(saved_idx, len(self.commits) - 1))
            self._scroll_into_view()

    @bind_action(
        "toggle_report", "ctrl r", desc="Toggle commit report (contribution graph)"
    )
    def toggle_report(self) -> None:
        """Toggle the bottom contribution-graph report strip."""
        self._report_enabled = not self._report_enabled
        self._report_band.enabled = self._report_enabled
        h = self._size[1] if self._size else 0
        if h <= self.REPORT_MIN_HEIGHT:
            show_toast(
                f"Need more than {self.REPORT_MIN_HEIGHT} rows for the commit report",
                duration=2.0,
                kind=FeedbackKind.WARNING,
            )
        self.invalidate_chrome_bands()
        self._scroll_into_view()
        self._request_render()

    @bind_action("search", "/", desc="Filter commit list by message or SHA")
    def search(self) -> None:
        """Activate the commit-list search filter."""
        self.enter_search()

    def _source_index(self, item_idx: int) -> int:
        """Map a visible item index to the source index in ``_all_commits``."""
        if item_idx < len(self._source_map):
            return self._source_map[item_idx]
        return item_idx

    @bind_action("copy_sha", "Y", desc="Copy commit SHA to clipboard")
    def copy_sha(self) -> None:
        """Copy the selected commit SHA to the clipboard."""
        commit = self._current_commit()
        if commit is None:
            return
        run_async(
            lambda: copy_to_clipboard(commit.sha),
            lambda ok, sha=commit.sha: (
                show_toast(f"Copied {sha[:7]}", duration=1.5, kind=FeedbackKind.SUCCESS)
                if ok
                else show_toast(
                    "Failed to copy to clipboard",
                    duration=2.0,
                    kind=FeedbackKind.ERROR,
                )
            ),
        )

    def get_help_title(self) -> str:
        if self._vm.viewing_checkout_log():
            return "Commit"
        return f"Commit · {self._vm.log_ref}"

    def _current_commit(self) -> Commit | None:
        """Return the commit at ``curr_no`` (item index in either mode)."""
        if not self.commits:
            return None
        if 0 <= self.curr_no < len(self.commits):
            return self.commits[self.curr_no]
        return None

    def get_inspector_snapshot(self) -> CommitSnapshot | None:
        """Return a frozen snapshot for the selected commit."""
        source_idx = self._source_index(self.curr_no)
        return self._vm.get_inspector_snapshot(source_idx)

    def mount(self) -> None:
        super().mount()
        self._bind_vm_signals()
        self._vm.refresh()

    def unmount(self) -> None:
        super().unmount()
        self._unbind_vm_signals()

    def set_vm(self, vm: ICommitViewModel) -> None:
        """Retarget this panel to a new Commit ViewModel (repo session switch).

        Session owns VM lifetime; this only rebinds signals and reloads.
        """
        self._unbind_vm_signals()
        self._vm = vm
        if self.is_mounted():
            self._bind_vm_signals()
            self._vm.refresh()

    def _unbind_vm_signals(self) -> None:
        """Drop subscriptions to the current ViewModel (if any)."""
        for unsub in self._vm_unsubs:
            unsub()
        self._vm_unsubs.clear()

    def _bind_vm_signals(self) -> None:
        """Bind vm.items signal; safe to call multiple times (idempotent)."""
        if not self._vm_unsubs:
            self._vm_unsubs.append(
                bind_signals(self, self._vm.items, callback=self._on_items_changed)
            )

    def _on_items_changed(self) -> None:
        if not self.is_mounted():
            return
        commits = self._vm.items.value
        self._all_commits = list(commits)
        # Clear decoration / body caches BEFORE rebuild so row templates
        # re-parse ``extra_info`` (e.g. HEAD moved off a former tip).
        self._bodies = None
        self._body_lines_cache.clear()
        self._refs_cache.clear()
        self._apply_filter()
        self._contrib_graph.set_commits(commits)

    def _apply_filter(self) -> None:
        """Filter commits by query and rebuild display state."""
        query = self.search_query.lower()
        if not query:
            self.commits = list(self._all_commits)
            self._source_map = list(range(len(self._all_commits)))
        else:
            filtered: list[Commit] = []
            mapping: list[int] = []
            for i, c in enumerate(self._all_commits):
                if (
                    query in c.msg.lower()
                    or query in c.author.lower()
                    or query in c.sha.lower()
                ):
                    filtered.append(c)
                    mapping.append(i)
            self.commits = filtered
            self._source_map = mapping
        if not self.commits:
            self.set_content(["No matching commits."])
            self._max_meta_w = 0
            self._row_cache.clear()
            self._notify_change()
            return
        self._rel_time_cache.clear()
        self._abs_time_cache.clear()
        for commit in self.commits:
            self._rel_time_cache[commit.sha] = relative_time(commit.unix_timestamp)
            self._abs_time_cache[commit.sha] = self._format_abs_time(
                commit.unix_timestamp
            )
        if self._expanded:
            self._ensure_bodies()
        self._rebuild_rows()
        self._build_row_cache()
        self._notify_change()

    def _handle_result(self, result: ActionResult) -> None:
        if result.success:
            show_badge(result.message, duration=1.0, kind=FeedbackKind.SUCCESS)
        else:
            show_toast(result.message, duration=2.0, kind=FeedbackKind.ERROR)
        if result.should_refresh:
            self._vm.refresh()

    def _ensure_bodies(self) -> None:
        if self._bodies is not None or not self.commits:
            return
        self._bodies = self._vm.get_bodies()
        self._body_lines_cache.clear()

    def _body_lines(self, commit: Commit) -> list[str]:
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

    def _schema_for(self, commit: Commit) -> list[tuple[_SubRow, int]]:
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

    def _format_compact(self, commit: Commit) -> str:
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

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
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
        # Placeholder ("No commits found.") — the only case where content
        # outranks commits.
        if not self.commits:
            cursor_flags = palette.STYLE_BOLD if is_cursor else 0
            return (
                [
                    Segment(
                        self.content[idx],
                        fg=self.presentation_fg("muted"),
                        style_flags=cursor_flags,
                    )
                ],
                None,
                [],
            )

        if item_idx is not None:
            commit = self.commits[item_idx]
            kind, payload = self._schema_for(commit)[sub_row]
            if kind is _SubRow.COMMIT:
                left, main = self._commit_left_main(commit, item_idx, is_cursor)
                return left, main, []
            return self._describe_sub_row(commit, item_idx, kind, payload)

        # Compact: cache is full-strength only; cursor or inactive rebuilds live.
        commit = self.commits[idx]
        if is_cursor or not self.is_presentation_active():
            return self._describe_compact(commit, idx, is_cursor)

        if idx < len(self._row_cache):
            left_tpl, main_tpl = self._row_cache[idx]
            return (
                list(left_tpl),
                list(main_tpl),
                self._meta_segments(commit, bake_active=False, is_cursor=False),
            )

        return self._describe_compact(commit, idx, False)

    def _describe_compact(
        self,
        commit: Commit,
        item_idx: int,
        is_cursor: bool,
    ) -> tuple[list[Segment], list[Segment], list[Segment]]:
        left, main = self._commit_left_main(commit, item_idx, is_cursor)
        right = self._meta_segments(commit, is_cursor=is_cursor)
        if is_cursor:
            right = [
                Segment(
                    s.text,
                    fg=s.fg,
                    bg=s.bg,
                    style_flags=palette.STYLE_BOLD,
                )
                for s in right
            ]
        return left, main, right

    def _is_head_commit(self, commit: Commit) -> bool:
        """Return True when git decoration marks this commit as HEAD."""
        cached = self._refs_cache.get(commit.sha)
        if cached is None:
            cached = _parse_decoration(commit.extra_info, self._vm.remotes)
            self._refs_cache[commit.sha] = cached
        head_ref, _, _ = cached
        return head_ref != ""

    def _selected_row_bg(self, *, bake_active: bool = False) -> tuple[int, int, int]:
        """Background for the cursor-selected commit row."""
        if bake_active or self.is_presentation_active():
            return THEME.bg_commit_selected
        return THEME.bg_commit_selected_inactive

    def _commit_left_main(
        self,
        commit: Commit,
        item_idx: int,
        is_cursor: bool,
        *,
        bake_active: bool = False,
    ) -> tuple[list[Segment], list[Segment]]:
        """Build rails + sha + refs + subject; cursor mark comes from OptionList.

        ``bake_active`` forces primary/muted/graph colors for the active cache
        (steal / non-leaf must not be baked — those rebuild live via ``presentation_fg``).
        """
        cursor_flags = palette.STYLE_BOLD if is_cursor else 0
        fg_primary = (
            THEME.fg_primary if bake_active else self.presentation_fg("primary")
        )
        fg_muted = THEME.fg_muted if bake_active else self.presentation_fg("muted")
        graph_active = bake_active or self.is_presentation_active()
        row_bg = self._selected_row_bg(bake_active=bake_active) if is_cursor else None

        left: list[Segment] = [Segment(self.GRAPH_PAD, fg=fg_primary, bg=row_bg)]

        source_idx = self._source_index(item_idx)
        if source_idx < len(self._vm.graph_rows):
            left.extend(
                self._render_rails(
                    self._vm.graph_rows[source_idx],
                    commit,
                    cursor_flags=cursor_flags,
                    graph_active=graph_active,
                    row_bg=row_bg,
                )
            )

        left.append(
            Segment(
                commit.sha[:7],
                fg=fg_muted,
                style_flags=cursor_flags,
                bg=row_bg,
            )
        )
        left.append(Segment(" ", fg=fg_primary, bg=row_bg))

        main: list[Segment] = self._ref_segments(
            commit,
            cursor_flags=cursor_flags,
            row_bg=row_bg,
        )
        main.append(
            Segment(
                commit.msg,
                fg=fg_primary,
                style_flags=cursor_flags,
                bg=row_bg,
            )
        )
        return left, main

    def _build_row_cache(self) -> None:
        """Pre-build per-commit (left, main) Segments for full-strength presentation.

        Cursor styling, steal, and non-leaf soften are excluded; those rebuild live.
        """
        self._row_cache = []
        for idx, commit in enumerate(self.commits):
            left, main = self._commit_left_main(
                commit, idx, is_cursor=False, bake_active=True
            )
            self._row_cache.append((tuple(left), tuple(main)))

    def _meta_segments(
        self,
        commit: Commit,
        *,
        bake_active: bool = False,
        is_cursor: bool = False,
    ) -> list[Segment]:
        author = commit.author
        rel = self._rel_time_cache.get(commit.sha) or relative_time(
            commit.unix_timestamp
        )
        meta = f"  {author}  {rel}"
        meta_w = wcswidth(meta)
        reserve = max(self._max_meta_w, meta_w)
        if reserve > meta_w:
            meta = " " * (reserve - meta_w) + meta
        row_bg = self._selected_row_bg(bake_active=bake_active) if is_cursor else None
        fg = THEME.fg_muted if bake_active else self.presentation_fg("muted")
        return [Segment(meta, fg=fg, style_flags=0, bg=row_bg)]

    def _describe_sub_row(
        self,
        commit: Commit,
        item_idx: int,
        kind: _SubRow,
        payload: int,
    ) -> tuple[list[Segment], list[Segment], list[Segment]]:
        """Render a non-COMMIT sub-row (Merge:/Author:/Date:/blank/body line).

        The cursor only ever lives on a COMMIT row, so sub-rows are never
        styled bold and we omit ``cursor_flags`` entirely.
        """
        fg_primary = self.presentation_fg("primary")
        fg_muted = self.presentation_fg("muted")
        left: list[Segment] = [Segment(self.GRAPH_PAD, fg=fg_primary)]
        source_idx = self._source_index(item_idx)
        if source_idx < len(self._vm.graph_rows):
            left.extend(
                self._render_rails(
                    self._vm.graph_rows[source_idx],
                    None,
                    sub=True,
                    cursor_flags=0,
                    graph_active=self.is_presentation_active(),
                )
            )

        if kind in (_SubRow.BLANK, _SubRow.TAIL):
            return left, [], []

        if kind is _SubRow.MERGE:
            text = " ".join(p[:7] for p in commit.parents)
            main = [
                Segment("Merge: ", fg=fg_muted),
                Segment(text, fg=fg_primary),
            ]
        elif kind is _SubRow.AUTHOR:
            main = [
                Segment("Author: ", fg=fg_muted),
                Segment(commit.author, fg=fg_primary),
            ]
        elif kind is _SubRow.DATE:
            text = self._abs_time_cache.get(commit.sha) or self._format_abs_time(
                commit.unix_timestamp
            )
            main = [
                Segment("Date:   ", fg=fg_muted),
                Segment(text, fg=fg_primary),
            ]
        elif kind is _SubRow.MESSAGE:
            body_lines = self._body_lines(commit)
            text = body_lines[payload] if 0 <= payload < len(body_lines) else ""
            main = [
                Segment("    ", fg=fg_primary),
                Segment(text, fg=fg_primary),
            ]
        else:
            main = []
        return left, main, []

    def _ref_segments(
        self,
        commit: Commit,
        *,
        cursor_flags: int,
        row_bg: tuple[int, int, int] | None = None,
    ) -> list[Segment]:
        """Render branch-ref badges wrapped in orange parens, comma-separated."""
        cached = self._refs_cache.get(commit.sha)
        if cached is None:
            cached = _parse_decoration(commit.extra_info, self._vm.remotes)
            self._refs_cache[commit.sha] = cached
        head_ref, local_refs, remote_refs = cached
        if not (head_ref or local_refs or remote_refs or commit.tag):
            return []

        paren_fg = THEME.fg_tag_parent
        head_fg = THEME.fg_info
        local_fg = THEME.fg_local_branch
        remote_fg = THEME.fg_remote_branch
        tag_fg = THEME.fg_tag
        arrow_fg = THEME.fg_primary

        seg_bg = row_bg

        entries: list[list[Segment]] = []
        if head_ref == "HEAD":
            entries.append(
                [Segment("HEAD", fg=head_fg, style_flags=cursor_flags, bg=seg_bg)]
            )
        elif head_ref:
            entries.append(
                [
                    Segment("HEAD", fg=head_fg, style_flags=cursor_flags, bg=seg_bg),
                    Segment(" -> ", fg=arrow_fg, style_flags=cursor_flags, bg=seg_bg),
                    Segment(head_ref, fg=local_fg, style_flags=cursor_flags, bg=seg_bg),
                ]
            )
        for name in local_refs:
            entries.append(
                [Segment(name, fg=local_fg, style_flags=cursor_flags, bg=seg_bg)]
            )
        for name in remote_refs:
            entries.append(
                [Segment(name, fg=remote_fg, style_flags=cursor_flags, bg=seg_bg)]
            )
        if commit.tag:
            entries.append(
                [Segment(commit.tag[0], fg=tag_fg, style_flags=cursor_flags, bg=seg_bg)]
            )

        segs: list[Segment] = [
            Segment("(", fg=paren_fg, style_flags=cursor_flags, bg=seg_bg)
        ]
        for i, entry in enumerate(entries):
            if i > 0:
                segs.append(
                    Segment(", ", fg=paren_fg, style_flags=cursor_flags, bg=seg_bg)
                )
            segs.extend(entry)
        segs.append(Segment(") ", fg=paren_fg, style_flags=cursor_flags, bg=seg_bg))
        return segs

    def _render_rails(
        self,
        row: GraphRow,
        commit: Commit | None,
        *,
        sub: bool = False,
        cursor_flags: int,
        graph_active: bool,
        row_bg: tuple[int, int, int] | None = None,
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
                        Segment(
                            "  ",
                            fg=THEME.fg_dim,
                            style_flags=cursor_flags,
                            bg=row_bg,
                        )
                    )
                    continue
                lanes = THEME.graph_lane_colors
                color = lanes[i % len(lanes)]
                fg = color if graph_active else THEME.fg_dim
                segments.append(
                    Segment(
                        self.GRAPH_VERTICAL + " ",
                        fg=fg,
                        style_flags=cursor_flags,
                        bg=row_bg,
                    )
                )
            return segments

        total_lanes = max(len(row.lanes_before), len(row.lanes_after))
        segments = []
        assert commit is not None
        for i in range(total_lanes):
            ch, fg = self._lane_glyph(row, i, commit, graph_active=graph_active)
            segments.append(
                Segment(
                    ch + " ",
                    fg=fg,
                    style_flags=cursor_flags,
                    bg=row_bg,
                )
            )
        return segments

    def _lane_glyph(
        self,
        row: GraphRow,
        i: int,
        commit: Commit,
        *,
        graph_active: bool,
    ) -> tuple[str, tuple[int, int, int]]:
        """Pick the glyph and color for lane ``i`` on this row."""
        lanes = THEME.graph_lane_colors
        lane_color = lanes[i % len(lanes)]
        lane_fg = lane_color if graph_active else THEME.fg_dim

        if i == row.commit_lane:
            if not commit.is_pushed():
                # Unpushed wins over HEAD so local-only tip stays yellow.
                return self.GRAPH_COMMIT, THEME.fg_unpushed_commit
            if self._is_head_commit(commit):
                return self.GRAPH_COMMIT, THEME.fg_head_commit
            return self.GRAPH_COMMIT, lane_color if graph_active else THEME.fg_dim

        if i in row.closed_lanes:
            return self.GRAPH_CLOSE, lane_fg

        if i in row.opened_lanes:
            return self.GRAPH_OPEN, lane_fg

        before_active = i < len(row.lanes_before) and row.lanes_before[i] is not None
        after_active = i < len(row.lanes_after) and row.lanes_after[i] is not None
        if before_active or after_active:
            return self.GRAPH_VERTICAL, lane_fg

        return " ", THEME.fg_dim

    def capture_key(self, key: str) -> bool:
        if self.search_handle_key(key):
            return True
        return self.search_active
