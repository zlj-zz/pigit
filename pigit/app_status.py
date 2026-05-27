"""
Module: pigit/app_status.py
Description: StatusPanel v3 with whole-row backgrounds, filter, and visual mode.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

import logging
import os
from enum import Enum, auto
from typing import TYPE_CHECKING
from collections.abc import Callable

_logger = logging.getLogger(__name__)

from pigit.termui import (
    ActionEventType,
    AlertDialog,
    bind_keys,
    bind_signals,
    by_id,
    exec_external,
    keys,
    palette,
    Segment,
    show_badge,
    show_toast,
)
from pigit.termui.widgets import ItemList

from .app_diff import DiffType, DiffViewer
from .app_inspector import FileInfo
from .app_preview import PreviewPanel
from .app_search_filter import SearchFilter
from .app_theme import THEME
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
        return THEME.accent_green
    if ch in "RC":
        return THEME.accent_yellow
    if ch == "?":
        return THEME.accent_blue
    if ch == "U":
        return THEME.accent_red
    return THEME.fg_muted


def _unstaged_fg(ch: str, focused: bool) -> tuple[int, int, int]:
    if not focused:
        return THEME.fg_dim
    if ch in "MD":
        return THEME.accent_red
    if ch in "RC":
        return THEME.accent_yellow
    if ch == "?":
        return THEME.accent_blue
    if ch == "U":
        return THEME.accent_red
    return THEME.fg_muted


def _label_fg(label: str, focused: bool) -> tuple[int, int, int]:
    """Return a semantic color for the status label."""
    if not focused:
        return THEME.fg_dim
    match label:
        case "Staged":
            return THEME.accent_green
        case "Modified":
            return THEME.accent_red
        case "Mixed":
            return THEME.accent_yellow
        case "Conflict":
            return THEME.accent_red
        case "Deleted":
            return THEME.accent_red
        case "Untracked":
            return THEME.accent_blue
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


class StatusPanel(ItemList):
    """Status panel with visual mode."""

    CURSOR = "●"  # filled circle

    def __init__(
        self,
        *,
        alert_inner_width: int | None = None,
        on_selection_changed: Callable | None = None,
        vm: IStatusViewModel,
        id: str | None = None,
    ) -> None:
        super().__init__(
            on_selection_changed=on_selection_changed,
            empty_state=[
                Segment("    (\\__/)", fg=THEME.accent_green),
                Segment("    ( •_• )", fg=THEME.accent_green),
                Segment("    / > ✓", fg=THEME.accent_green),
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

        # Visual mode state
        self._visual_mode = False
        self._visual_anchor: int | None = None
        self._selected: set[int] = set()
        self._visual_scroll = False  # auto-select while navigating

    def filter_source_index(self, visible_idx: int | None = None) -> int:
        """Map a visible (filtered) index back to the source data index."""
        idx = self.curr_no if visible_idx is None else visible_idx
        return self._filter.source_index(idx)

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
            self.set_content([])
            self._notify_change()
            return
        self.set_content([f.name for f in self.files])
        self._notify_change()

    @bind_keys("j", keys.KEY_DOWN)
    def next(self, step: int = 1) -> None:
        super().next(step)
        if (
            self._visual_mode
            and self._visual_scroll
            and self._visual_anchor is not None
        ):
            self._update_visual_selection()

    @bind_keys("k", keys.KEY_UP)
    def previous(self, step: int = 1) -> None:
        super().previous(step)
        if (
            self._visual_mode
            and self._visual_scroll
            and self._visual_anchor is not None
        ):
            self._update_visual_selection()

    def _update_visual_selection(self) -> None:
        """Update selected indices based on visual anchor and current position."""
        if self._visual_anchor is None:
            return
        start = min(self._visual_anchor, self.curr_no)
        end = max(self._visual_anchor, self.curr_no)
        self._selected.update(range(start, end + 1))

    @bind_keys("J")
    def _scroll_preview_down(self) -> None:
        preview = by_id("preview", PreviewPanel)
        if preview is not None:
            preview.scroll_down(DiffViewer.SCROLL_PAGE_SIZE)

    @bind_keys("K")
    def _scroll_preview_up(self) -> None:
        preview = by_id("preview", PreviewPanel)
        if preview is not None:
            preview.scroll_up(DiffViewer.SCROLL_PAGE_SIZE)

    @bind_keys("v")
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

    @bind_keys("s")
    def toggle_visual_scroll(self) -> None:
        """Toggle visual scroll mode (auto-select while navigating)."""
        if not self._visual_mode:
            return
        self._visual_scroll = not self._visual_scroll
        if self._visual_scroll:
            self._visual_anchor = self.curr_no
            self._update_visual_selection()
        self._notify_mode()

    @bind_keys(keys.KEY_SPACE)
    def toggle_space_selection(self) -> None:
        """Toggle selection of current file in visual mode."""
        if not self._visual_mode:
            return
        idx = self.curr_no
        if idx in self._selected:
            self._selected.discard(idx)
        else:
            self._selected.add(idx)

    def resize(self, size: tuple[int, int]) -> None:
        super().resize(size)
        self._alert_dialog.resize(size)
        if not self.files:
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
        """Return row description: [cursor][staged][unstaged][filename.......][label]"""
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

        is_selected = idx in self._selected
        if is_selected:
            filename_fg = THEME.accent_purple if focused else THEME.fg_dim
        else:
            filename_fg = fg_primary
        main = [Segment(file.name, fg=filename_fg, style_flags=cursor_flags)]

        right: list[Segment] = []
        label = _status_label(file)
        if label:
            right.append(Segment(label, fg=_label_fg(label, focused)))

        return left, main, right

    def on_key(self, key: str) -> None:
        if self._filter.handle_key(key):
            return

        if not self.files:
            return
        if key == keys.KEY_ENTER:
            source_idx = self._filter.source_index(self.curr_no)
            diff = self._vm.load_diff(source_idx)
            f = self.files[self.curr_no]
            diff_type = (
                DiffType.STAGED
                if (f.has_staged_change and not f.has_unstaged_change)
                else DiffType.UNSTAGED
            )
            self.emit(
                ActionEventType.goto,
                target="diff",
                source=self,
                key=f.name,
                content=diff,
                repo_path=self._vm.repo_path,
                diff_type=diff_type,
            )
            return
        if key == "a":
            _logger.debug("[STATUS] on_key: stage")
            f = self.files[self.curr_no]
            if f.has_merged_conflicts or f.has_inline_merged_conflicts:
                self._check_via_alert(
                    self._vm.stage, self.curr_no, msg="Stage conflicted file"
                )
            else:
                action = "Unstaged" if f.has_staged_change else "Staged"
                self._run_action(
                    self._vm.stage,
                    single_msg=f"{action} {f.name}",
                    batch_msg="Updated {} file(s)",
                    action_type=StatusAction.STAGE,
                )
            return
        if key == "i":
            self._run_action(
                self._vm.ignore,
                single_msg="Ignored",
                batch_msg="Ignored {} file(s)",
                action_type=StatusAction.IGNORE,
            )
            return
        if key == "d":
            _logger.debug("[STATUS] on_key: discard")
            self._run_action(
                self._vm.discard,
                single_msg="Discard file",
                batch_msg="Discard {} file(s)",
                action_type=StatusAction.DISCARD,
                needs_confirm=True,
            )
            return
        if key == "C":
            if not any(f.has_staged_change for f in self.files):
                show_toast("No staged changes to commit", duration=2.0)
                return
            try:
                result = exec_external(["git", "commit"], cwd=self._vm.repo_path)
                if result.returncode == 0:
                    show_toast("Commit created", duration=1.5)
                else:
                    show_toast("Commit aborted or failed", duration=2.0)
            except Exception:
                show_toast("Failed to open editor", duration=2.0)
                raise
            finally:
                self._vm.refresh()
            return
        if key == "E":
            self._open_external_editor(self.files[self.curr_no])
            return
        if key == "o":
            source_idx = self._filter.source_index(self.curr_no)
            result = self._vm.checkout_ours(source_idx)
            self._handle_result(result)
            return
        if key == "t":
            source_idx = self._filter.source_index(self.curr_no)
            result = self._vm.checkout_theirs(source_idx)
            self._handle_result(result)
            return
        if key == "z":
            result = self._vm.stash_push()
            self._handle_result(result)
            return

    # --- Helpers ---

    def _handle_result(self, result: ActionResult) -> None:
        """Handle a ViewModel action result: badge/toast and optional refresh."""
        _logger.debug(
            "[STATUS] _handle_result: success=%s should_refresh=%s msg=%r",
            result.success,
            result.should_refresh,
            result.message,
        )
        if result.success:
            show_badge(result.message, duration=1.0)
        else:
            show_toast(result.message, duration=2.0)
        if result.should_refresh:
            self._vm.refresh()

    def _open_external_editor(self, file: File) -> None:
        """Open file in external editor, suspending TUI."""
        editor = os.environ.get("EDITOR", "vim")
        try:
            exec_external([editor, file.name], cwd=self._vm.repo_path)
        except Exception:
            show_toast("Failed to open editor", duration=2.0)
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
        self.emit(ActionEventType.mode_changed, mode=mode)

    def get_help_title(self) -> str:
        return "Status"

    def get_help_entries(self) -> list[tuple[str, str]]:
        """Return help pairs based on current mode."""
        if self._visual_mode:
            if self._visual_scroll:
                return [
                    ("jk/↑↓", "Navigate & select"),
                    ("s", "Exit scroll mode"),
                ]
            return [
                ("jk/↑↓", "Navigate"),
                ("Space", "Select"),
                ("a", "Stage selected"),
                ("d", "Discard selected"),
                ("i", "Ignore selected"),
                ("v", "Exit visual"),
                ("s", "Toggle scroll mode"),
            ]
        entries = [
            ("jk/↑↓", "Navigate"),
            ("Enter", "Open"),
            ("/", "Filter"),
            ("a", "Stage"),
            ("d", "Discard"),
            ("i", "Ignore"),
            ("C", "Commit"),
            ("v", "Visual"),
            ("E", "Edit file"),
        ]
        if (
            self.files
            and 0 <= self.curr_no < len(self.files)
            and self.files[self.curr_no].has_merged_conflicts
        ):
            entries.extend([("o", "Ours"), ("t", "Theirs")])
        return entries

    def get_inspector_data(self) -> FileInfo | None:
        """Return inspector data for the currently selected file."""
        source_idx = self._filter.source_index(self.curr_no)
        return self._vm.get_inspector_data(source_idx)

    def _toast_no_selection(self) -> None:
        """Show toast when no files are selected in visual mode."""
        show_toast("No files selected", duration=2.0)

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
    ) -> None:
        """Unified handler for single / visual mode actions."""
        if self._visual_mode:
            if self._visual_scroll:
                show_toast("Press s to exit scroll mode", duration=2.0)
                return
            if not self._selected:
                self._toast_no_selection()
                return
            if needs_confirm:
                self._confirm_batch(batch_msg, action_type)
                return
            result = self._dispatch_batch(action_type, self._selected)
            self._handle_result(result)
            self._clear_visual_mode()
            return
        # Single mode
        source_idx = self._filter.source_index(self.curr_no)
        if needs_confirm:
            if self._check_via_alert(callee, self.curr_no, msg=single_msg):
                return
        else:
            result = callee(source_idx)
            self._handle_result(result)

    def _dispatch_batch(
        self, action_type: StatusAction, indices: set[int]
    ) -> ActionResult:
        source_indices = {self._filter.source_index(i) for i in indices}
        match action_type:
            case StatusAction.STAGE:
                return self._vm.stage_indices(source_indices)
            case StatusAction.DISCARD:
                return self._vm.discard_indices(source_indices)
            case StatusAction.IGNORE:
                return self._vm.ignore_indices(source_indices)
        return ActionResult(success=False, message="Unknown action")

    def _check_via_alert(
        self,
        callee: Callable[[int], ActionResult],
        idx: int,
        msg: str = "",
    ) -> bool:
        file = self.files[idx]
        text = f"{msg} '{file}' ?"
        source_idx = self._filter.source_index(idx)

        def on_result(confirmed: bool) -> None:
            if not confirmed:
                self._vm.refresh()
                return
            result = callee(source_idx)
            self._handle_result(result)
            if self.files:
                self.curr_no = min(max(self.curr_no, 0), len(self.files) - 1)

        return self._alert_dialog.alert(text, on_result)

    def _confirm_batch(self, action: str, action_type: StatusAction) -> None:
        """Confirm a batch operation on selected files."""
        count = len(self._selected)
        text = f"{action} {count} files?"

        def on_result(confirmed: bool) -> None:
            if not confirmed:
                return
            result = self._dispatch_batch(action_type, self._selected)
            self._handle_result(result)
            self._selected.clear()
            self._visual_mode = False
            self._visual_anchor = None

        self._alert_dialog.alert(text, on_result)
