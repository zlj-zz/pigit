# -*- coding: utf-8 -*-
"""
Module: pigit/app_status.py
Description: StatusPanel v3 with whole-row backgrounds, filter, and visual mode.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

from pigit.termui import (
    ActionEventType,
    AlertDialog,
    bind_keys,
    Component,
    exec_external,
    ItemSelector,
    keys,
    show_badge,
    show_toast,
)
from pigit.termui.wcwidth_table import wcswidth

from .app_inspector import FileInfo
from .app_theme import THEME
from .git.model import File

if TYPE_CHECKING:
    from .git.local_git import LocalGit
    from .git.repo import GitFileT, GitFuncT


def _staged_fg(ch: str) -> tuple[int, int, int]:
    if ch in "MA":
        return THEME.accent_green
    if ch == "?":
        return THEME.accent_blue
    return THEME.fg_dim


def _unstaged_fg(ch: str) -> tuple[int, int, int]:
    if ch in "MD":
        return THEME.accent_red
    if ch == "?":
        return THEME.accent_blue
    return THEME.fg_dim


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


class StatusPanel(ItemSelector):
    """Status panel with visual mode."""

    CURSOR = "\u25cf"  # filled circle

    def __init__(
        self,
        *,
        alert_inner_width: Optional[int] = None,
        display: Optional[Component] = None,
        on_visual_mode_changed: Optional[Callable] = None,
        on_selection_changed: Optional[Callable] = None,
        git: "LocalGit",
    ) -> None:
        super().__init__(
            on_selection_changed=on_selection_changed,
            lazy_load=True,
        )
        self.git = git
        self._display = display
        self._on_visual_mode_changed = on_visual_mode_changed

        self.files: list[File] = []
        self._all_files: list[File] = []  # For filter reset
        self._alert_dialog = AlertDialog(
            inner_width=alert_inner_width,
            on_result=lambda _: None,
        )

        # Visual mode state
        self._visual_mode = False
        self._visual_anchor: Optional[int] = None
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
        self.files = self.git.load_status()
        self._all_files = list(self.files)
        if not self.files:
            self.set_content(["No status changed."])
            return
        # content is only used for row-count bookkeeping; rendering uses
        # describe_row which reads directly from self.files.
        self.set_content([f.name for f in self.files])

    def resize(self, size: tuple[int, int]) -> None:
        super().resize(size)
        self._alert_dialog.resize(size)

    def _render_surface(self, surface) -> None:
        if self.files:
            super()._render_surface(surface)
            return

        w = surface.width
        h = surface.height
        if w <= 0 or h <= 0:
            return

        art_lines = [
            "    (\\__/)",
            "    ( \u2022_\u2022 )",
            "    / > \u2713",
            "  Pigit Clean",
            "Working tree clean",
        ]

        total_height = len(art_lines)
        start_row = (h - total_height) // 2

        for i, line in enumerate(art_lines):
            row = start_row + i
            line_w = wcswidth(line)
            col = max(0, (w - line_w) // 2)
            fg = THEME.accent_green if i < 3 else THEME.fg_dim
            surface.draw_text_rgb(row, col, line, fg=fg)

    def describe_row(self, idx: int, is_cursor: bool) -> tuple[
        list[tuple[str, tuple[int, int, int], bool]],
        list[tuple[str, tuple[int, int, int], bool]] | None,
        list[tuple[str, tuple[int, int, int], bool]],
    ]:
        """Return row description: [cursor][staged][unstaged][filename.......][label]"""
        focused = self.is_focus_leaf
        if idx >= len(self.files):
            text = self.content[idx] if idx < len(self.content) else ""
            prefix = self.CURSOR if is_cursor else " "
            fg = THEME.fg_primary if focused else THEME.fg_dim
            return ([(f"{prefix} {text}", fg, is_cursor)], None, [])

        file = self.files[idx]
        staged = file.short_status[0] if len(file.short_status) > 0 else " "
        unstaged = file.short_status[1] if len(file.short_status) > 1 else " "
        cursor_prefix = self.CURSOR if is_cursor else " "

        fg_primary = THEME.fg_primary if focused else THEME.fg_dim
        left = [
            (cursor_prefix, fg_primary, is_cursor),
            (" ", fg_primary, False),
            (staged, _staged_fg(staged), is_cursor),
            (unstaged, _unstaged_fg(unstaged), is_cursor),
            (" ", fg_primary, False),
        ]

        is_selected = idx in self._selected
        if is_selected:
            filename_fg = THEME.accent_purple if focused else THEME.fg_dim
        else:
            filename_fg = fg_primary
        main = [(file.name, filename_fg, is_cursor)]

        right: list[tuple[str, tuple[int, int, int], bool]] = []
        label = _status_label(file)
        if label:
            right.append((label, THEME.fg_muted if focused else THEME.fg_dim, False))

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
                target=self._display,
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

    # --- Helpers ---

    def _notify_mode(self) -> None:
        """Notify parent of current visual mode state."""
        if self._on_visual_mode_changed is not None:
            if not self._visual_mode:
                mode = ""
            elif self._visual_scroll:
                mode = "Visual-scroll"
            else:
                mode = "Visual"
            self._on_visual_mode_changed(mode)

    def get_help_title(self) -> str:
        return "Status"

    def get_help_entries(self) -> list[tuple[str, str]]:
        """Return help pairs based on current mode."""
        if self._visual_mode:
            if self._visual_scroll:
                return [
                    ("j/k", "Navigate & select"),
                    ("s", "Exit scroll mode"),
                ]
            return [
                ("j/k", "Navigate"),
                ("Space", "Select"),
                ("a", "Stage selected"),
                ("d", "Discard selected"),
                ("i", "Ignore selected"),
                ("v", "Exit visual"),
                ("s", "Toggle scroll mode"),
            ]
        return [
            ("j/k", "Navigate"),
            ("Enter", "Open"),
            ("a", "Stage"),
            ("d", "Discard"),
            ("i", "Ignore"),
            ("C", "Commit"),
            ("v", "Visual"),
        ]

    def get_inspector_data(self) -> Optional[FileInfo]:
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
        file: GitFileT,
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
