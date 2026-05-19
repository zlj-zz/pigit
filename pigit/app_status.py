"""
Module: pigit/app_status.py
Description: StatusPanel v3 with whole-row backgrounds, filter, and visual mode.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from collections.abc import Callable

from pigit.termui import (
    ActionEventType,
    AlertDialog,
    bind_keys,
    exec_external,
    keys,
    palette,
    Segment,
    show_badge,
    show_toast,
)
from pigit.termui._async_task import AsyncTask
from pigit.termui.widgets import ItemList

from .app_inspector import FileInfo
from .app_theme import THEME
from .git.model import File

if TYPE_CHECKING:
    from .git.local_git import LocalGit
    from .git.model import GitFuncT


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

    CURSOR = "\u25cf"  # filled circle

    def __init__(
        self,
        *,
        alert_inner_width: int | None = None,
        on_selection_changed: Callable | None = None,
        git: LocalGit,
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
        self.git = git
        self._loader = AsyncTask()

        self.files: list[File] = []
        self._all_files: list[File] = []  # For filter reset
        self._alert_dialog = AlertDialog(
            inner_width=alert_inner_width,
            on_result=lambda _: None,
        )

        # Visual mode state
        self._visual_mode = False
        self._visual_anchor: int | None = None
        self._selected: set[int] = set()
        self._visual_scroll = False  # auto-select while navigating

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

    def refresh(self) -> None:
        self._loader.start(self.git.load_status, self._on_status_loaded)

    def _on_status_loaded(self, files: list[File]) -> None:
        if not self.is_activated():
            return
        self.files = files
        self._all_files = list(files)
        if not files:
            self.set_content([])
        else:
            # content is only used for row-count bookkeeping; rendering uses
            # describe_row which reads directly from self.files.
            self.set_content([f.name for f in files])

    def deactivate(self) -> None:
        super().deactivate()
        self._loader.cancel()

    def resize(self, size: tuple[int, int]) -> None:
        super().resize(size)
        self._alert_dialog.resize(size)
        if not self.files:
            self.set_content([])

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
        if not self.files:
            return
        f = self.files[self.curr_no]
        if key == keys.KEY_ENTER:
            cached = f.has_staged_change and not f.has_unstaged_change
            c = self.git.load_file_diff(f.name, f.tracked, cached, plain=True).split(
                "\n"
            )
            self.emit(
                ActionEventType.goto,
                target="diff",
                source=self,
                key=f.name,
                content=c,
            )
            return
        if key == "a":
            action = "Unstaged" if f.has_staged_change else "Staged"
            self._run_action(
                self.git.switch_file_status,
                single_msg=f"{action} {f.name}",
                batch_msg="Updated {} file(s)",
            )
            return
        if key == "i":
            self._run_action(
                self.git.ignore_file,
                single_msg="Ignored",
                batch_msg="Ignored {} file(s)",
            )
            return
        if key == "d":
            self._run_action(
                self.git.discard_file,
                single_msg="Discard file",
                batch_msg="Discard {} file(s)",
                needs_confirm=True,
            )
            return
        if key == "C":
            if not any(f.has_staged_change for f in self.files):
                show_toast("No staged changes to commit", duration=2.0)
                return
            try:
                result = exec_external(["git", "commit"], cwd=self.git.path)
                if result.returncode == 0:
                    show_toast("Commit created", duration=1.5)
                else:
                    show_toast("Commit aborted or failed", duration=2.0)
            except Exception:
                show_toast("Failed to open editor", duration=2.0)
                raise
            finally:
                self.refresh()
            return
        if key == "E":
            self._open_external_editor(f)
            return
        if key == "o" and f.has_merged_conflicts:
            try:
                self.git.checkout_ours(f)
                self.git.add_file(f)
                show_badge("Ours", duration=1.0)
            except Exception as e:
                show_toast(f"Ours failed: {e}", duration=2.0)
            self.refresh()
            return
        if key == "t" and f.has_merged_conflicts:
            try:
                self.git.checkout_theirs(f)
                self.git.add_file(f)
                show_badge("Theirs", duration=1.0)
            except Exception as e:
                show_toast(f"Theirs failed: {e}", duration=2.0)
            self.refresh()
            return

    # --- Helpers ---

    def _open_external_editor(self, file: File) -> None:
        """Open file in external editor, suspending TUI."""
        editor = os.environ.get("EDITOR", "vim")
        try:
            exec_external([editor, file.name], cwd=self.git.path)
        except Exception:
            show_toast("Failed to open editor", duration=2.0)
        finally:
            self.refresh()

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
        return [
            ("jk/↑↓", "Navigate"),
            ("Enter", "Open"),
            ("a", "Stage"),
            ("d", "Discard"),
            ("i", "Ignore"),
            ("C", "Commit"),
            ("v", "Visual"),
            ("E", "Edit file"),
            ("o", "Ours"),
            ("t", "Theirs"),
        ]

    def get_inspector_data(self) -> FileInfo | None:
        """Return inspector data for the currently selected file."""
        idx = self.curr_no
        if not self.files or not (0 <= idx < len(self.files)):
            return None
        file = self.files[idx]
        size, mtime = ("?", "?")
        if self.git is not None:
            size, mtime = self.git.get_file_info(file)
        return FileInfo(file=file, size=size, mtime=mtime)

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
        callee: GitFuncT,
        *,
        single_msg: str = "",
        batch_msg: str = "",
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
                self._confirm_batch(batch_msg, callee)
            else:
                count = len(self._selected)
                for idx in sorted(self._selected):
                    if idx < len(self.files):
                        callee(self.files[idx])
                self._clear_visual_mode()
                show_badge(batch_msg.format(count), duration=1.5)
        else:
            f = self.files[self.curr_no]
            if needs_confirm:
                if self._check_via_alert(callee, f, msg=single_msg):
                    return
            else:
                callee(f)
                show_badge(single_msg, duration=1.5)
        self.refresh()

    def _check_via_alert(
        self,
        callee: GitFuncT,
        file: File,
        msg: str = "",
    ) -> bool:
        text = f"{msg} '{file}' ?"

        def on_result(confirmed: bool) -> None:
            if not confirmed:
                self.refresh()
                return
            callee(file)
            self.refresh()
            if self.files:
                self.curr_no = min(max(self.curr_no, 0), len(self.files) - 1)
            show_badge(msg, duration=1.5)

        return self._alert_dialog.alert(text, on_result)

    def _confirm_batch(self, action: str, callee: GitFuncT) -> None:
        """Confirm a batch operation on selected files."""
        count = len(self._selected)
        text = f"{action} {count} files?"

        def on_result(confirmed: bool) -> None:
            if not confirmed:
                return
            for idx in sorted(self._selected):
                if idx < len(self.files):
                    callee(self.files[idx])
            self._selected.clear()
            self._visual_mode = False
            self._visual_anchor = None
            self.refresh()
            show_badge(f"{action} {count} file(s)", duration=1.5)

        self._alert_dialog.alert(text, on_result)
