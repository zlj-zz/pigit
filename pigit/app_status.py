"""
Module: pigit/app_status.py
Description: StatusPanel v3 with whole-row backgrounds, filter, and visual mode.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING
from collections.abc import Callable

_logger = logging.getLogger(__name__)

from pigit.termui import (
    EventType,
    FeedbackKind,
    EVT_GOTO,
    AlertDialog,
    bind_action,
    bind_signals,
    by_id,
    dismiss_sheet,
    exec_external,
    keys,
    palette,
    Segment,
    show_badge,
    show_sheet,
    show_toast,
)
from pigit.termui.tty_io import terminal_size
from pigit.termui.widgets import ItemList

from .app_diff import DiffType, DiffViewer
from .app_types import FileInfo
from .app_preview import PreviewPanel
from .app_search_filter import SearchFilter
from .app_theme import THEME
from .ext.utils import copy_to_clipboard
from pigit.termui._async_task import run_async
from .git.model import File
from .viewmodels.base import ActionResult

if TYPE_CHECKING:
    from pigit.viewmodels.status import IStatusViewModel


class StatusAction(Enum):
    """Action types for status panel batch operations."""

    STAGE = auto()
    DISCARD = auto()
    IGNORE = auto()


def _staged_fg(ch: str, focused: bool) -> tuple[int, int, int]:
    if not focused:
        return THEME.fg_dim
    if ch in "MA":
        return THEME.fg_success
    if ch in "RC":
        return THEME.fg_warning
    if ch == "?":
        return THEME.fg_info
    if ch == "U":
        return THEME.fg_danger
    return THEME.fg_muted


def _unstaged_fg(ch: str, focused: bool) -> tuple[int, int, int]:
    if not focused:
        return THEME.fg_dim
    if ch in "MD":
        return THEME.fg_danger
    if ch in "RC":
        return THEME.fg_warning
    if ch == "?":
        return THEME.fg_info
    if ch == "U":
        return THEME.fg_danger
    return THEME.fg_muted


def _label_fg(label: str, focused: bool) -> tuple[int, int, int]:
    """Return a semantic color for the status label."""
    if not focused:
        return THEME.fg_dim
    match label:
        case "Staged":
            return THEME.fg_success
        case "Modified":
            return THEME.fg_danger
        case "Mixed":
            return THEME.fg_warning
        case "Conflict":
            return THEME.fg_danger
        case "Deleted":
            return THEME.fg_danger
        case "Untracked":
            return THEME.fg_info
        case _:
            return THEME.fg_muted


def _status_label(file: File) -> str:
    """Return a human-readable status label."""
    if file.has_merged_conflicts:
        return "Conflict"
    if file.deleted:
        return "Deleted"
    if not file.tracked:
        return "Untracked"
    if file.has_staged_change and file.has_unstaged_change:
        return "Mixed"
    if file.has_staged_change:
        return "Staged"
    if file.has_unstaged_change:
        return "Modified"
    return ""


@dataclass(slots=True)
class StatusTreeRow:
    """A row in the status tree: a directory node or a file node."""

    kind: str  # "dir" | "file"
    path: str  # Full relative path (directory or file path)
    name: str  # Display name (basename)
    depth: int  # Indent depth (0 = top level)
    file: File | None  # Non-None for file nodes; None for directory nodes
    source_index: int  # Source index into _all_files for files; -1 for dirs
    child_indices: frozenset[int] = frozenset()  # Dirs: all file source indices below
    summary: str = ""  # Dirs: change summary


@dataclass
class _DirNode:
    """Internal node for tree building."""

    path: str
    subdirs: set[str] = field(default_factory=set)
    files: list[tuple[File, int]] = field(default_factory=list)
    all_files: list[File] = field(default_factory=list)
    all_indices: set[int] = field(default_factory=set)


# Summary display order, kept stable.
_SUMMARY_ORDER = ("Conflict", "Staged", "Modified", "Deleted", "Untracked", "Mixed")


def _summarize(files: list[File]) -> str:
    """Summarize status labels of files, e.g. "N modified · M added"."""
    counts: dict[str, int] = {}
    for f in files:
        label = _status_label(f)
        if label:
            counts[label] = counts.get(label, 0) + 1
    parts = [f"{counts[k]} {k.lower()}" for k in _SUMMARY_ORDER if counts.get(k)]
    return " · ".join(parts) if parts else ""


def build_status_tree(
    items: list[tuple[File, int]],
    collapsed_dirs: set[str],
) -> list[StatusTreeRow]:
    """Group (File, source_index) into a directory tree and flatten to rows.

    Args:
        items: (File, source_index into _all_files) pairs, sorted/filtered as needed.
        collapsed_dirs: Set of collapsed directory paths.

    Returns:
        Tree rows: directories before files (each alphabetical);
        collapsed directories' children are omitted.
    """
    dirs: dict[str, _DirNode] = {}
    root_files: list[tuple[File, int]] = []

    def _ensure_dir(path: str) -> _DirNode:
        if path not in dirs:
            dirs[path] = _DirNode(path=path)
        return dirs[path]

    # 1. Split paths, create implicit intermediate dirs; rename target, normalize separator.
    for f, src_idx in items:
        path = f.get_file_str().replace("\\", "/")
        if "/" not in path:
            root_files.append((f, src_idx))
            continue
        parts = path.split("/")
        for i in range(1, len(parts)):
            _ensure_dir("/".join(parts[:i]))
        _ensure_dir("/".join(parts[:-1])).files.append((f, src_idx))

    # 2. Link parent-child directory relationships.
    for d in list(dirs):
        if "/" in d:
            parent = d.rsplit("/", 1)[0]
            if parent in dirs:
                dirs[parent].subdirs.add(d.rsplit("/", 1)[-1])

    # 3. Post-order fill all_files / all_indices.
    def _fill(node: _DirNode) -> None:
        for sub in sorted(node.subdirs):
            child_path = f"{node.path}/{sub}" if node.path else sub
            _fill(dirs[child_path])
            child = dirs[child_path]
            node.all_files.extend(child.all_files)
            node.all_indices |= child.all_indices
        node.all_files.extend(f for f, _ in node.files)
        node.all_indices |= {i for _, i in node.files}

    top_dirs = sorted(d for d in dirs if "/" not in d)
    for d in top_dirs:
        _fill(dirs[d])

    # 4. Pre-order flatten: render the dir itself, then children (depth+1).
    rows: list[StatusTreeRow] = []

    def _walk(prefix: str, depth: int) -> None:
        node = dirs[prefix]
        rows.append(
            StatusTreeRow(
                kind="dir",
                path=prefix,
                name=prefix.rsplit("/", 1)[-1],
                depth=depth,
                file=None,
                source_index=-1,
                child_indices=frozenset(node.all_indices),
                summary=_summarize(node.all_files),
            )
        )
        if prefix in collapsed_dirs:
            return
        for sub in sorted(node.subdirs):
            _walk(f"{prefix}/{sub}", depth + 1)
        for f, idx in sorted(node.files, key=lambda x: x[0].name):
            p = f.get_file_str().replace("\\", "/")
            rows.append(
                StatusTreeRow(
                    kind="file",
                    path=p,
                    name=p.rsplit("/", 1)[-1],
                    depth=depth + 1,
                    file=f,
                    source_index=idx,
                )
            )

    for d in top_dirs:
        _walk(d, 0)
    for f, idx in sorted(root_files, key=lambda x: x[0].name):
        p = f.get_file_str().replace("\\", "/")
        rows.append(
            StatusTreeRow(
                kind="file",
                path=p,
                name=p.rsplit("/", 1)[-1],
                depth=0,
                file=f,
                source_index=idx,
            )
        )
    return rows


class StatusPanel(ItemList):
    """Status panel with visual mode."""

    CURSOR = "●"  # filled circle
    keymap_namespace = "status"

    def __init__(
        self,
        *,
        alert_inner_width: int | None = None,
        on_selection_changed: Callable | None = None,
        vm: IStatusViewModel,
        default_view: str = "tree",
        id: str | None = None,
    ) -> None:
        super().__init__(
            on_selection_changed=on_selection_changed,
            empty_state=[
                Segment("    (\\__/)", fg=THEME.fg_success),
                Segment("    ( •_• )", fg=THEME.fg_success),
                Segment("    / > ✓", fg=THEME.fg_success),
                Segment("  Pigit Clean", fg=THEME.fg_dim),
                Segment("Working tree clean", fg=THEME.fg_dim),
            ],
            lazy_load=True,
            id=id,
        )
        self._vm = vm
        self.files: list[File] = []
        self._all_files: list[File] = []
        self._filter = SearchFilter(self._apply_filter)
        self._alert_dialog = AlertDialog(
            inner_width=alert_inner_width,
            on_result=lambda _: None,
        )
        self._vm_unsubs: list[Callable[[], None]] = []

        # Tree view state
        self._tree_mode = default_view == "tree"
        self._collapsed_dirs: set[str] = set()
        self._tree_rows: list[StatusTreeRow] = []

        # Visual mode state
        self._visual_mode = False
        self._visual_anchor: int | None = None
        self._selected: set[int] = set()
        self._visual_scroll = False  # auto-select while navigating

    def activate(self) -> None:
        super().activate()
        self._bind_vm_signals()
        self._vm.refresh()

    def deactivate(self) -> None:
        super().deactivate()
        for unsub in self._vm_unsubs:
            unsub()
        self._vm_unsubs.clear()
        self._vm.dispose()

    def _bind_vm_signals(self) -> None:
        """Bind vm.items signal; safe to call multiple times (idempotent)."""
        if not self._vm_unsubs:
            self._vm_unsubs.append(
                bind_signals(self, self._vm.items, callback=self._on_items_changed)
            )

    def _on_items_changed(self) -> None:
        files = self._vm.items.value
        _logger.debug(
            "[STATUS] _on_items_changed: activated=%s files=%d",
            self.is_activated(),
            len(files),
        )
        if not self.is_activated():
            return
        self._all_files = list(files)
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Filter files by query and rebuild display state."""
        query = self._filter.query.lower()
        if not query:
            self.files = list(self._all_files)
            self._filter.map = list(range(len(self._all_files)))
        else:
            filtered: list[File] = []
            mapping: list[int] = []
            for i, f in enumerate(self._all_files):
                if query in f.name.lower():
                    filtered.append(f)
                    mapping.append(i)
            self.files = filtered
            self._filter.map = mapping
        if not self.files:
            self._tree_rows = []
            self.set_content([])
            self._notify_change()
            return
        if self._tree_mode:
            self._auto_expand_matches()
            self._prune_collapsed_dirs()
            items = list(zip(self.files, self._filter.map))
            self._tree_rows = build_status_tree(items, self._collapsed_dirs)
            self.set_content([row.name for row in self._tree_rows])
        else:
            self._tree_rows = []
            self.set_content([f.name for f in self.files])
        self._notify_change()

    def _auto_expand_matches(self) -> None:
        """Expand parent dirs of filter matches so they stay visible."""
        if not self._filter.query:
            return
        for f in self.files:
            parts = f.get_file_str().replace("\\", "/").split("/")[:-1]
            for i in range(1, len(parts) + 1):
                self._collapsed_dirs.discard("/".join(parts[:i]))

    def _prune_collapsed_dirs(self) -> None:
        """Drop stale collapsed paths (dirs no longer present, based on all files)."""
        valid: set[str] = set()
        for f in self._all_files:
            parts = f.get_file_str().replace("\\", "/").split("/")[:-1]
            for i in range(1, len(parts) + 1):
                valid.add("/".join(parts[:i]))
        self._collapsed_dirs &= valid

    @bind_action("next", "j", "down", desc="Navigate file list", tip="Navigate")
    def next(self, step: int = 1) -> None:
        super().next(step)
        if (
            self._visual_mode
            and self._visual_scroll
            and self._visual_anchor is not None
        ):
            self._update_visual_selection()

    @bind_action("previous", "k", "up", desc="Navigate file list", tip="Navigate")
    def previous(self, step: int = 1) -> None:
        super().previous(step)
        if (
            self._visual_mode
            and self._visual_scroll
            and self._visual_anchor is not None
        ):
            self._update_visual_selection()

    @bind_action(
        "preview_down",
        "J",
        desc="Scroll preview down (not in visual mode)",
        tip="Preview Navigate",
        tip_when=lambda self: not self._visual_mode,
    )
    def _scroll_preview_down(self) -> None:
        preview = by_id("preview", PreviewPanel)
        if preview is not None:
            preview.scroll_down(DiffViewer.SCROLL_PAGE_SIZE)

    @bind_action(
        "preview_up",
        "K",
        desc="Scroll preview up (not in visual mode)",
        tip="Preview Navigate",
        tip_when=lambda self: not self._visual_mode,
    )
    def _scroll_preview_up(self) -> None:
        preview = by_id("preview", PreviewPanel)
        if preview is not None:
            preview.scroll_up(DiffViewer.SCROLL_PAGE_SIZE)

    @bind_action(
        "open_diff",
        "enter",
        desc="Open diff for selected file (not in visual mode)",
        tip="Open",
        tip_when=lambda self: not self._visual_mode,
    )
    def open_diff(self) -> None:
        if self._tree_mode:
            row = self._row(self.curr_no)
            if row is not None and row.kind == "dir":
                self._toggle_collapse(row.path)
                return
        hit = self.file_at_cursor()
        if hit is None:
            return
        f, source_idx = hit
        diff = self._vm.load_diff(source_idx)
        diff_type = (
            DiffType.STAGED
            if (f.has_staged_change and not f.has_unstaged_change)
            else DiffType.UNSTAGED
        )
        self.emit(
            EVT_GOTO,
            target="diff",
            source=self,
            key=f.name,
            content=diff,
            repo_path=self._vm.repo_path,
            diff_type=diff_type,
        )

    @bind_action("stage", "a", desc="Stage current file or selection", tip="Stage")
    def stage(self) -> None:
        _logger.debug("[STATUS] stage")
        if self._tree_mode and not self._visual_mode:
            row = self._row(self.curr_no)
            if row is not None and row.kind == "dir":
                self._dir_action(StatusAction.STAGE, row)
                return
        hit = self.file_at_cursor()
        if hit is None:
            return
        f = hit[0]
        if f.has_merged_conflicts or f.has_inline_merged_conflicts:
            self._check_via_alert(self._vm.stage, msg="Stage conflicted file")
        else:
            action = "Unstaged" if f.has_staged_change else "Staged"
            self._run_action(
                self._vm.stage,
                single_msg=f"{action} {f.name}",
                batch_msg="Updated {} file(s)",
                action_type=StatusAction.STAGE,
            )

    @bind_action(
        "commit",
        "c",
        desc="Open inline commit editor (not in visual mode)",
        tip="Commit",
        tip_when=lambda self: not self._visual_mode,
    )
    def commit(self) -> None:
        if not self._vm.staged_files:
            show_toast(
                "No staged changes to commit",
                duration=1.5,
                kind=FeedbackKind.WARNING,
            )
            return
        from .app_commit_editor import CommitEditor

        def _do_commit(msg: str) -> None:
            subject = msg.split("\n", 1)[0].strip()
            result = self._vm.commit(msg)
            if result.success:
                dismiss_sheet()
                self._vm.refresh()
                show_badge(
                    f"Committed: {subject}", duration=1.5, kind=FeedbackKind.SUCCESS
                )
            else:
                show_toast(result.message, duration=2.0, kind=FeedbackKind.ERROR)

        editor = CommitEditor(
            vm=self._vm,
            staged_files=self._vm.staged_files,
            on_submit=_do_commit,
            on_cancel=dismiss_sheet,
        )
        rows = terminal_size()[1]
        show_sheet(
            editor,
            height=min(rows - 2, max(10, int(rows * 0.35))),
            show_border=True,
        )
        editor.activate()

    @bind_action(
        "amend",
        "A",
        desc="Amend last commit with staged changes (not in visual mode)",
    )
    def amend(self) -> None:
        """Confirm, then amend HEAD with staged changes (``--amend --no-edit``)."""
        if self._visual_mode:
            return
        if not self._vm.staged_files:
            show_toast(
                "No staged changes to amend",
                duration=1.5,
                kind=FeedbackKind.WARNING,
            )
            return

        def on_result(confirmed: bool) -> None:
            if not confirmed:
                return
            result = self._vm.amend()
            if result.success:
                self._vm.refresh()
                show_badge("Amended HEAD", duration=1.5, kind=FeedbackKind.SUCCESS)
            else:
                show_toast(result.message, duration=2.0, kind=FeedbackKind.ERROR)

        self._alert_dialog.alert(
            "Amend last commit with staged changes?",
            on_result,
            destructive=True,
        )

    @bind_action(
        "commit_editor",
        "C",
        desc="Open external $EDITOR for commit (not in visual mode)",
        tip="Commit",
        tip_when=lambda self: not self._visual_mode,
    )
    def commit_editor(self) -> None:
        if not any(f.has_staged_change for f in self.files):
            show_toast(
                "No staged changes to commit",
                duration=2.0,
                kind=FeedbackKind.WARNING,
            )
            return
        try:
            result = exec_external(["git", "commit"], cwd=self._vm.repo_path)
            if result.returncode == 0:
                show_toast("Commit created", duration=1.5, kind=FeedbackKind.SUCCESS)
            else:
                show_toast(
                    "Commit aborted or failed",
                    duration=2.0,
                    kind=FeedbackKind.ERROR,
                )
        except Exception:
            show_toast("Failed to open editor", duration=2.0, kind=FeedbackKind.ERROR)
            raise
        finally:
            self._vm.refresh()

    @bind_action(
        "discard",
        "d",
        desc="Discard changes irreversibly (confirm if modified)",
        tip="Discard",
    )
    def discard(self) -> None:
        _logger.debug("[STATUS] discard")
        if self._tree_mode and not self._visual_mode:
            row = self._row(self.curr_no)
            if row is not None and row.kind == "dir":
                self._dir_action(StatusAction.DISCARD, row)
                return
        self._run_action(
            self._vm.discard,
            single_msg="Discard file",
            batch_msg="Discard {} file(s)",
            action_type=StatusAction.DISCARD,
            needs_confirm=True,
            destructive=True,
        )

    @bind_action(
        "stash",
        "s",
        desc="Stash working tree including untracked (not in visual mode)",
        tip="Stash",
        tip_when=lambda self: not self._visual_mode,
    )
    def stash(self) -> None:
        result = self._vm.stash_push()
        self._handle_result(result)

    @bind_action(
        "visual_mode", "v", desc="Toggle visual multi-select mode", tip="Visual"
    )
    def toggle_visual_mode(self) -> None:
        """Toggle visual (multi-select) mode."""
        if not self.files:
            return
        self._visual_mode = not self._visual_mode
        if self._visual_mode:
            self._visual_anchor = self.curr_no
            self._selected = set()
            self._visual_scroll = False
        else:
            self._visual_anchor = None
            self._selected.clear()
            self._visual_scroll = False
        self._notify_mode()

    @bind_action(
        "visual_scroll",
        "V",
        desc="Toggle visual scroll mode (visual mode)",
        tip="V-scroll",
        tip_when=lambda self: self._visual_mode,
    )
    def toggle_visual_scroll(self) -> None:
        """Toggle visual scroll mode (auto-select while navigating)."""
        if not self._visual_mode:
            return
        self._visual_scroll = not self._visual_scroll
        if self._visual_scroll:
            self._visual_anchor = self.curr_no
            self._update_visual_selection()
        self._notify_mode()

    @bind_action(
        "toggle_select",
        " ",
        desc="Toggle selection of current row (visual mode)",
        tip="Select",
        tip_when=lambda self: self._visual_mode,
    )
    def toggle_space_selection(self) -> None:
        """Toggle selection of current row in visual mode (source-index based)."""
        if not self._visual_mode:
            return
        if not self._tree_mode:
            idx = self._filter.source_index(self.curr_no)
            if idx in self._selected:
                self._selected.discard(idx)
            else:
                self._selected.add(idx)
            return
        row = self._row(self.curr_no)
        if row is None:
            return
        if row.kind == "dir":
            if row.child_indices and row.child_indices <= self._selected:
                self._selected -= row.child_indices
            else:
                self._selected |= row.child_indices
        elif row.source_index >= 0:
            if row.source_index in self._selected:
                self._selected.discard(row.source_index)
            else:
                self._selected.add(row.source_index)

    @bind_action("search", "/", desc="Filter file list by name")
    def search(self) -> None:
        """Activate the file-list search filter."""
        self._filter.enter()

    @bind_action("toggle_tree", "T", desc="Toggle tree / flat file view")
    def toggle_tree(self) -> None:
        self._toggle_tree_mode()

    @bind_action("expand_dir", "l", "right", desc="Expand directory (tree view)")
    def expand_dir(self) -> None:
        self._expand_current_dir()

    @bind_action("collapse_dir", "h", "left", desc="Collapse directory (tree view)")
    def collapse_dir(self) -> None:
        self._collapse_current_dir()

    @bind_action(
        "open_editor",
        "E",
        desc="Open file in external $EDITOR (not in visual mode)",
        tip="Edit",
        tip_when=lambda self: not self._visual_mode,
    )
    def open_editor(self) -> None:
        hit = self.file_at_cursor()
        if hit is not None:
            self._open_external_editor(hit[0])

    @bind_action("ignore", "i", desc="Add file to .gitignore")
    def ignore(self) -> None:
        if self._tree_mode and not self._visual_mode:
            row = self._row(self.curr_no)
            if row is not None and row.kind == "dir":
                self._dir_action(StatusAction.IGNORE, row)
                return
        self._run_action(
            self._vm.ignore,
            single_msg="Ignored",
            batch_msg="Ignored {} file(s)",
            action_type=StatusAction.IGNORE,
        )

    @bind_action(
        "checkout_ours",
        "o",
        desc="Checkout ours on conflict (discards theirs; not in visual mode)",
        tip="Ours",
        tip_when=lambda self: not self._visual_mode and self._cursor_has_conflict(),
    )
    def checkout_ours(self) -> None:
        hit = self.file_at_cursor()
        if hit is not None:
            result = self._vm.checkout_ours(hit[1])
            self._handle_result(result)

    @bind_action(
        "checkout_theirs",
        "t",
        desc="Checkout theirs on conflict (discards ours; not in visual mode)",
        tip="Theirs",
        tip_when=lambda self: not self._visual_mode and self._cursor_has_conflict(),
    )
    def checkout_theirs(self) -> None:
        hit = self.file_at_cursor()
        if hit is not None:
            result = self._vm.checkout_theirs(hit[1])
            self._handle_result(result)

    @bind_action("copy_path", "Y", desc="Copy file path")
    def copy_path(self) -> None:
        hit = self.file_at_cursor()
        if hit is not None:
            path = hit[0].name
            run_async(
                lambda: copy_to_clipboard(path),
                lambda ok, p=path: (
                    show_toast(f"Copied: {p}", duration=1.0, kind=FeedbackKind.SUCCESS)
                    if ok
                    else show_toast(
                        "Failed to copy to clipboard",
                        duration=2.0,
                        kind=FeedbackKind.ERROR,
                    )
                ),
            )

    def _update_visual_selection(self) -> None:
        """Update selection based on visual anchor and cursor, in source indices."""
        if self._visual_anchor is None:
            return
        start = min(self._visual_anchor, self.curr_no)
        end = max(self._visual_anchor, self.curr_no)
        if not self._tree_mode:
            self._selected.update(
                self._filter.source_index(i) for i in range(start, end + 1)
            )
            return
        for idx in range(start, end + 1):
            row = self._row(idx)
            if row is None:
                continue
            if row.kind == "dir":
                self._selected |= row.child_indices
            elif row.source_index >= 0:
                self._selected.add(row.source_index)

    def resize(self, size: tuple[int, int]) -> None:
        super().resize(size)
        self._alert_dialog.resize(size)
        if not self.files:
            self._tree_rows = []
            self.set_content([])

    def _render_surface(self, surface) -> None:
        super()._render_surface(surface)
        self._filter.render_bar(surface)

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
        """Split render into tree/flat modes instead of stacking if-branches."""
        if self._tree_mode:
            return self._describe_tree_row(idx, is_cursor)
        return self._describe_flat_row(idx, is_cursor)

    def _describe_flat_row(
        self, idx: int, is_cursor: bool
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        """Render a flat-view row (original behavior)."""
        focused = self.is_focus_leaf
        if not self.files or idx >= len(self.files):
            return ([], None, [])
        file = self.files[idx]
        staged = file.short_status[0] if len(file.short_status) > 0 else " "
        unstaged = file.short_status[1] if len(file.short_status) > 1 else " "
        cursor_prefix = self.CURSOR if is_cursor else " "

        fg_primary = THEME.fg_primary if focused else THEME.fg_dim
        cursor_flags = palette.STYLE_BOLD if is_cursor else 0
        left = [
            Segment(cursor_prefix, fg=fg_primary, style_flags=cursor_flags),
            Segment(" ", fg=fg_primary),
            Segment(staged, fg=_staged_fg(staged, focused), style_flags=cursor_flags),
            Segment(
                unstaged, fg=_unstaged_fg(unstaged, focused), style_flags=cursor_flags
            ),
            Segment(" ", fg=fg_primary),
        ]

        is_selected = self._filter.source_index(idx) in self._selected
        if is_selected:
            filename_fg = THEME.fg_staged_renamed if focused else THEME.fg_dim
        else:
            filename_fg = fg_primary
        main = [Segment(file.name, fg=filename_fg, style_flags=cursor_flags)]

        right: list[Segment] = []
        label = _status_label(file)
        if label:
            right.append(Segment(label, fg=_label_fg(label, focused)))

        return left, main, right

    def _describe_tree_row(
        self, idx: int, is_cursor: bool
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        """Render a tree row: dir (arrow + summary) or file (indent + status)."""
        row = self._row(idx)
        if row is None:
            return ([], None, [])
        focused = self.is_focus_leaf
        indent = "  " * row.depth
        cursor_prefix = self.CURSOR if is_cursor else " "
        fg_primary = THEME.fg_primary if focused else THEME.fg_dim
        cursor_flags = palette.STYLE_BOLD if is_cursor else 0

        if row.kind == "dir":
            arrow = "▶" if row.path in self._collapsed_dirs else "▼"
            left = [
                Segment(cursor_prefix, fg=fg_primary, style_flags=cursor_flags),
                Segment(" ", fg=fg_primary),
            ]
            main = [
                Segment(
                    indent + arrow + " " + row.name + "/",
                    fg=fg_primary,
                    style_flags=cursor_flags,
                )
            ]
            right = [Segment(row.summary, fg=THEME.fg_dim)] if row.summary else []
            return left, main, right

        file = row.file
        staged = file.short_status[0] if len(file.short_status) > 0 else " "
        unstaged = file.short_status[1] if len(file.short_status) > 1 else " "
        left = [
            Segment(cursor_prefix, fg=fg_primary, style_flags=cursor_flags),
            Segment(" ", fg=fg_primary),
            Segment(staged, fg=_staged_fg(staged, focused), style_flags=cursor_flags),
            Segment(
                unstaged, fg=_unstaged_fg(unstaged, focused), style_flags=cursor_flags
            ),
            Segment(" ", fg=fg_primary),
        ]
        is_selected = row.source_index in self._selected
        filename_fg = (
            THEME.fg_staged_renamed if (is_selected and focused) else fg_primary
        )
        main = [Segment(indent + row.name, fg=filename_fg, style_flags=cursor_flags)]

        right: list[Segment] = []
        label = _status_label(file)
        if label:
            right.append(Segment(label, fg=_label_fg(label, focused)))

        return left, main, right

    def _row(self, idx: int) -> StatusTreeRow | None:
        """Return the tree row at idx; None if not tree mode or out of range."""
        if not self._tree_mode or not self._tree_rows:
            return None
        if 0 <= idx < len(self._tree_rows):
            return self._tree_rows[idx]
        return None

    def file_at_cursor(self) -> tuple[File, int] | None:
        """Return (file, source_index) at cursor; None on dir row or no file."""
        if not self._tree_mode:
            if self.files and 0 <= self.curr_no < len(self.files):
                return self.files[self.curr_no], self._filter.source_index(self.curr_no)
            return None
        row = self._row(self.curr_no)
        if row is None or row.kind == "dir":
            return None
        return row.file, row.source_index

    def _cursor_has_conflict(self) -> bool:
        """Return True if the file at cursor has an unresolved merge conflict."""
        hit = self.file_at_cursor()
        return hit is not None and hit[0].has_merged_conflicts

    def capture_key(self, key: str) -> bool:
        if self._filter.handle_key(key):
            return True
        if self._filter.active:
            # While typing in the filter bar, ignore keys the filter did not
            # consume (e.g. arrow keys) so they don't trigger panel actions.
            return True
        # Clean tree: swallow panel actions, but let Tab bubble to the status
        # Column so focus can move to StashPanel.
        if not self.files:
            return key != keys.KEY_TAB
        return False

    # --- Helpers ---

    def _toggle_tree_mode(self) -> None:
        """Toggle flat / tree view."""
        self._tree_mode = not self._tree_mode
        self._apply_filter()

    def _toggle_collapse(self, dir_path: str) -> None:
        """Collapse/expand a directory and rebuild rows."""
        if dir_path in self._collapsed_dirs:
            self._collapsed_dirs.discard(dir_path)
        else:
            self._collapsed_dirs.add(dir_path)
        self._apply_filter()

    def _expand_current_dir(self) -> None:
        """Expand the current directory row (tree mode)."""
        row = self._row(self.curr_no)
        if row is not None and row.kind == "dir":
            self._collapsed_dirs.discard(row.path)
            self._apply_filter()

    def _collapse_current_dir(self) -> None:
        """Collapse the current directory row (tree mode)."""
        row = self._row(self.curr_no)
        if row is not None and row.kind == "dir":
            self._collapsed_dirs.add(row.path)
            self._apply_filter()

    def _dir_action(self, action_type: StatusAction, row: StatusTreeRow) -> None:
        """Run a batch action on a directory row (child_indices)."""
        indices = set(row.child_indices)
        if not indices:
            show_toast("No files in directory", duration=1.5, kind=FeedbackKind.WARNING)
            return
        if action_type == StatusAction.DISCARD:
            self._confirm_batch("Discard", action_type, indices, destructive=True)
            return
        result = self._dispatch_batch(action_type, indices)
        self._handle_result(result)

    def _handle_result(self, result: ActionResult) -> None:
        """Handle a ViewModel action result: badge/toast and optional refresh."""
        _logger.debug(
            "[STATUS] _handle_result: success=%s should_refresh=%s msg=%r",
            result.success,
            result.should_refresh,
            result.message,
        )
        if result.success:
            show_badge(result.message, duration=1.0, kind=FeedbackKind.SUCCESS)
        else:
            show_toast(result.message, duration=2.0, kind=FeedbackKind.ERROR)
        if result.should_refresh:
            self._vm.refresh()

    def _open_external_editor(self, file: File) -> None:
        """Open file in external editor, suspending TUI."""
        editor = os.environ.get("EDITOR", "vim")
        try:
            exec_external([editor, file.name], cwd=self._vm.repo_path)
        except Exception:
            show_toast("Failed to open editor", duration=2.0, kind=FeedbackKind.ERROR)
        finally:
            self._vm.refresh()

    def _notify_mode(self) -> None:
        """Notify parent of current visual mode state."""
        if not self._visual_mode:
            mode = ""
        elif self._visual_scroll:
            mode = "Visual-scroll"
        else:
            mode = "Visual"
        self.emit(EventType("mode_changed"), mode=mode)

    def get_help_title(self) -> str:
        return "Status"

    def get_inspector_data(self) -> FileInfo | None:
        """Return inspector data for the currently selected file."""
        hit = self.file_at_cursor()
        if hit is None:
            return None
        return self._vm.get_inspector_data(hit[1])

    def _toast_no_selection(self) -> None:
        """Show toast when no files are selected in visual mode."""
        show_toast("No files selected", duration=2.0, kind=FeedbackKind.WARNING)

    def _clear_visual_mode(self) -> None:
        """Exit visual mode and clear selection state."""
        self._selected.clear()
        self._visual_mode = False
        self._visual_anchor = None
        self._visual_scroll = False
        self._notify_mode()

    def _run_action(
        self,
        callee: Callable[[int], ActionResult],
        *,
        single_msg: str = "",
        batch_msg: str = "",
        action_type: StatusAction,
        needs_confirm: bool = False,
        destructive: bool = False,
    ) -> None:
        """Unified handler for single / visual mode actions."""
        if self._visual_mode:
            if self._visual_scroll:
                show_toast(
                    "Press V to exit scroll mode", duration=2.0, kind=FeedbackKind.INFO
                )
                return
            if not self._selected:
                self._toast_no_selection()
                return
            if needs_confirm:
                self._confirm_batch(batch_msg, action_type, destructive=destructive)
                return
            result = self._dispatch_batch(action_type, self._selected)
            self._handle_result(result)
            self._clear_visual_mode()
            return
        # Single mode
        hit = self.file_at_cursor()
        if hit is None:
            return
        _, source_idx = hit
        if needs_confirm:
            if self._check_via_alert(callee, msg=single_msg, destructive=destructive):
                return
        else:
            result = callee(source_idx)
            self._handle_result(result)

    def _dispatch_batch(
        self, action_type: StatusAction, indices: set[int]
    ) -> ActionResult:
        """Run a batch action on source-index set (indices are source indices)."""
        match action_type:
            case StatusAction.STAGE:
                return self._vm.stage_indices(indices)
            case StatusAction.DISCARD:
                return self._vm.discard_indices(indices)
            case StatusAction.IGNORE:
                return self._vm.ignore_indices(indices)
        return ActionResult(success=False, message="Unknown action")

    def _check_via_alert(
        self,
        callee: Callable[[int], ActionResult],
        msg: str = "",
        *,
        destructive: bool = False,
    ) -> bool:
        hit = self.file_at_cursor()
        if hit is None:
            return False
        file, source_idx = hit
        text = f"{msg} '{file}' ?"

        def on_result(confirmed: bool) -> None:
            if not confirmed:
                self._vm.refresh()
                return
            result = callee(source_idx)
            self._handle_result(result)
            n_rows = len(self._tree_rows) if self._tree_mode else len(self.files)
            if n_rows:
                self.curr_no = min(max(self.curr_no, 0), n_rows - 1)

        return self._alert_dialog.alert(text, on_result, destructive=destructive)

    def _confirm_batch(
        self,
        action: str,
        action_type: StatusAction,
        indices: set[int] | None = None,
        *,
        destructive: bool = False,
    ) -> None:
        """Confirm a batch operation on the given source indices (or selection)."""
        target = self._selected if indices is None else indices
        count = len(target)
        text = f"{action} {count} files?"

        def on_result(confirmed: bool) -> None:
            if not confirmed:
                return
            result = self._dispatch_batch(action_type, target)
            self._handle_result(result)
            self._selected.clear()
            self._visual_mode = False
            self._visual_anchor = None

        self._alert_dialog.alert(text, on_result, destructive=destructive)
