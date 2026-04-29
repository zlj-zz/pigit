# -*- coding: utf-8 -*-
"""
Module: pigit/app_branch.py
Description: BranchPanel v3 with ahead/behind display and current branch highlighting.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from pigit.termui import (
    bind_keys,
    ItemSelector,
    keys,
    show_toast,
    Signal,
)

from .app_inspector import BranchInfo
from .app_theme import THEME

if TYPE_CHECKING:
    from .git.local_git import LocalGit
    from .git.model import Branch


class BranchPanel(ItemSelector):
    """Branch panel with ahead/behind display and current branch highlighting."""

    CURSOR = "\u25cf"
    _SCOPES = ["local", "remote", "all"]
    _SCOPE_LABELS = {"local": "Local", "remote": "Remote", "all": "All"}

    def __init__(
        self,
        *,
        on_selection_changed: Optional[Callable] = None,
        branch_signal: Optional[Signal[str]] = None,
        git: "LocalGit",
    ) -> None:
        super().__init__(
            on_selection_changed=on_selection_changed,
            lazy_load=True,
        )
        self.git = git
        self._branch_signal = branch_signal
        self.branches: list[Branch] = []
        self._scope_idx: int = 0

    def refresh(self) -> None:
        scope = self._SCOPES[self._scope_idx]
        self.branches = branches = self.git.load_branches(scope=scope)
        if not branches:
            self.set_content([f"No {scope} branches found."])
            return
        lines = []
        for branch in branches:
            line = self._format_branch(branch)
            lines.append(line)
        self.set_content(lines)

    def get_help_title(self) -> str:
        return "Branch"

    def get_help_entries(self) -> list[tuple[str, str]]:
        """Return help pairs for branch panel."""
        scope_label = self._SCOPE_LABELS[self._SCOPES[self._scope_idx]]
        return [
            ("j/k", "Navigate"),
            ("c", "Checkout"),
            ("R", f"Scope ({scope_label})"),
        ]

    def get_inspector_data(self) -> Optional[BranchInfo]:
        """Return inspector data for the currently selected branch."""
        idx = self.curr_no
        if not self.branches or not (0 <= idx < len(self.branches)):
            return None
        b = self.branches[idx]
        recent_msg, recent_author, created = "?", "?", "?"
        if self.git is not None:
            recent_msg, recent_author = self.git.get_branch_recent_commit(b.name)
            created = self.git.get_branch_creation_time(b.name)
        return BranchInfo(
            branch=b,
            recent_msg=recent_msg,
            recent_author=recent_author,
            created=created,
        )

    def _format_branch(self, branch: "Branch") -> str:
        """Format a branch for display."""
        name = branch.name
        if name.startswith("remotes/"):
            name = name[len("remotes/") :]
        return name

    @bind_keys("j", keys.KEY_DOWN)
    def next(self, step: int = 1) -> None:
        super().next(step)

    @bind_keys("k", keys.KEY_UP)
    def previous(self, step: int = 1) -> None:
        super().previous(step)

    def describe_row(self, idx: int, is_cursor: bool) -> tuple[
        list[tuple[str, tuple[int, int, int], bool]],
        list[tuple[str, tuple[int, int, int], bool]] | None,
        list[tuple[str, tuple[int, int, int], bool]],
    ]:
        """Return row description: [cursor][branch_name.......][↑ahead ↓behind]"""
        focused = self.is_focus_leaf
        is_head = idx < len(self.branches) and self.branches[idx].is_head
        prefix = self.CURSOR if is_cursor else " "
        if is_head:
            fg = THEME.accent_green if focused else THEME.fg_dim
        else:
            fg = THEME.fg_primary if focused else THEME.fg_dim
        left = [(f"{prefix} {self.content[idx]}", fg, is_cursor)]

        right: list[tuple[str, tuple[int, int, int], bool]] = []
        if idx < len(self.branches):
            branch = self.branches[idx]
            if not branch.is_remote:
                ahead = branch.ahead if branch.ahead != "?" else ""
                behind = branch.behind if branch.behind != "?" else ""
                if ahead:
                    right.append((f"\u2191{ahead}", THEME.accent_green, False))
                if behind:
                    if right:
                        right.append((" ", THEME.fg_muted, False))
                    right.append((f"\u2193{behind}", THEME.accent_yellow, False))

        return left, None, right

    @bind_keys("R")
    def toggle_scope(self) -> None:
        """Cycle branch scope: local -> remote -> all -> local."""
        self._scope_idx = (self._scope_idx + 1) % len(self._SCOPES)
        scope = self._SCOPES[self._scope_idx]
        label = self._SCOPE_LABELS[scope]
        show_toast(f"Branch scope: {label}", duration=2.0)
        self.curr_no = 0
        self._r_start = 0
        self.refresh()

    def on_key(self, key: str) -> None:
        if key == "c":
            if not self.branches:
                return
            local_branch = self.branches[self.curr_no]
            if local_branch.is_head:
                show_toast("Already on this branch.", duration=1.5)
                return
            if local_branch.is_remote:
                show_toast("Cannot checkout remote branch directly.", duration=1.5)
                return
            try:
                self.git.checkout_branch(local_branch.name)
            except Exception as e:
                show_toast(f"Checkout failed: {e}", duration=3.0)
                return
            show_toast(f"Switched to {local_branch.name}", duration=1.5)
            if self._branch_signal is not None:
                self._branch_signal.set(local_branch.name)
            self.refresh()
