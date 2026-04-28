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

    def refresh(self) -> None:
        self.branches = branches = self.git.load_branches()
        if not branches:
            self.set_content(["No branches found."])
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
        return [
            ("j/k", "Navigate"),
            ("c", "Checkout"),
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
        return branch.name

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
        is_head = idx < len(self.branches) and self.branches[idx].is_head
        prefix = self.CURSOR if is_cursor else " "
        fg = THEME.accent_green if is_head else THEME.fg_primary
        left = [(f"{prefix} {self.content[idx]}", fg, is_cursor)]

        right: list[tuple[str, tuple[int, int, int], bool]] = []
        if idx < len(self.branches):
            branch = self.branches[idx]
            ahead = branch.ahead if branch.ahead != "?" else ""
            behind = branch.behind if branch.behind != "?" else ""
            if ahead:
                right.append((f"\u2191{ahead}", THEME.accent_green, False))
            if behind:
                if right:
                    right.append((" ", THEME.fg_muted, False))
                right.append((f"\u2193{behind}", THEME.accent_yellow, False))

        return left, None, right

    def on_key(self, key: str) -> None:
        if key == "c":
            if not self.branches:
                return
            local_branch = self.branches[self.curr_no]
            if local_branch.is_head:
                show_toast("Already on this branch.", duration=1.5)
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
