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
    AlertDialog,
    bind_keys,
    Component,
    LazyLoadMixin,
    ItemSelector,
    keys,
    show_badge,
    show_toast,
)
from pigit.termui.types import ActionLiteral
from pigit.termui._surface import _DEFAULT_BG
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth

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


class StatusPanel(LazyLoadMixin, ItemSelector):
    """Status panel with visual mode."""

    CURSOR = "\u25cf"  # filled circle

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        content: Optional[list[str]] = None,
        *,
        alert_inner_width: Optional[int] = None,
        display: Optional[Component] = None,
        on_visual_mode_changed: Optional[Callable] = None,
        on_selection_changed: Optional[Callable] = None,
        git: "LocalGit",
        repo_path: Optional[str] = None,
        repo_conf: Optional[str] = None,
    ) -> None:
        super().__init__(x, y, size, content, on_selection_changed=on_selection_changed)
        self.repo_path = repo_path
        self.repo_conf = repo_conf
        self.git = git
        self._display = display
        self._on_visual_mode_changed = on_visual_mode_changed

        self.files: list[File] = []
        self._all_files: list[File] = []  # For filter reset
        self._alert_dialog = AlertDialog(
            self,
            x=x,
            y=y,
            size=size,
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

    def fresh(self) -> None:
        self.files = self.git.load_status(self._size[0], plain=True)
        self._all_files = list(self.files)
        if not self.files:
            self.set_content(["No status changed."])
            return
        files_str = [f.display_str for f in self.files]
        self.set_content(files_str)

    def resize(self, size: tuple[int, int]) -> None:
        super().resize(size)
        self._alert_dialog.resize(size)

    def _render_surface(self, surface) -> None:
        if not self.content:
            return
        w = surface.width
        end = min(self._r_start + self._size[1], len(self.content))
        for idx in range(self._r_start, end):
            row = idx - self._r_start
            is_cursor = idx == self.curr_no

            line = self.content[idx]
            staged = line[0] if len(line) > 0 else " "
            unstaged = line[1] if len(line) > 1 else " "
            filename = line[3:] if len(line) > 3 else ""

            cursor_prefix = self.CURSOR if is_cursor else " "
            # Fixed prefix: cursor + space + staged + unstaged + space = 5 display columns
            fixed_width = 5

            if fixed_width >= w:
                # Not enough space; draw truncated prefix only
                surface.draw_text_rgb(
                    row,
                    0,
                    truncate_by_width(f"{cursor_prefix} {staged}{unstaged} ", w),
                    fg=THEME.fg_primary,
                    bg=_DEFAULT_BG,
                    bold=is_cursor,
                )
            else:
                col = 0
                surface.draw_text_rgb(
                    row,
                    col,
                    cursor_prefix,
                    fg=THEME.fg_primary,
                    bg=_DEFAULT_BG,
                    bold=is_cursor,
                )
                col += 1
                surface.draw_text_rgb(
                    row, col, " ", fg=THEME.fg_primary, bg=_DEFAULT_BG
                )
                col += 1
                surface.draw_text_rgb(
                    row,
                    col,
                    staged,
                    fg=_staged_fg(staged),
                    bg=_DEFAULT_BG,
                    bold=is_cursor,
                )
                col += 1
                surface.draw_text_rgb(
                    row,
                    col,
                    unstaged,
                    fg=_unstaged_fg(unstaged),
                    bg=_DEFAULT_BG,
                    bold=is_cursor,
                )
                col += 1
                surface.draw_text_rgb(
                    row, col, " ", fg=THEME.fg_primary, bg=_DEFAULT_BG
                )
                col += 1

                # Filename (truncate if needed)
                avail = w - fixed_width
                if wcswidth(filename) > avail:
                    filename = truncate_by_width(filename, avail - 1) + "\u2026"
                if filename:
                    is_selected = idx in self._selected
                    filename_fg = (
                        THEME.accent_purple if is_selected else THEME.fg_primary
                    )
                    surface.draw_text_rgb(
                        row,
                        col,
                        filename,
                        fg=filename_fg,
                        bg=_DEFAULT_BG,
                        bold=is_cursor,
                    )

            # Draw status label on the right
            if idx < len(self.files):
                label = _status_label(self.files[idx])
                label_w = wcswidth(label)
                if label_w < w - 4:
                    label_x = w - label_w
                    surface.draw_text_rgb(
                        row,
                        label_x,
                        label,
                        fg=THEME.fg_muted,
                        bg=_DEFAULT_BG,
                    )

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
                ActionLiteral.goto,
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
            ("v", "Visual"),
        ]

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
        self.fresh()

    def _check_via_alert(
        self,
        callee: GitFuncT,
        file: GitFileT,
        msg: str = "",
    ) -> bool:
        text = f"{msg} '{file}' ?"

        def on_result(confirmed: bool) -> None:
            if not confirmed:
                self.fresh()
                return
            callee(file)
            self.fresh()
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
            self.fresh()
            show_badge(f"{action} {count} file(s)", duration=1.5)

        self._alert_dialog.alert(text, on_result)
