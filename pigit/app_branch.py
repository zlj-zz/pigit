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
    LazyLoadMixin,
    ItemSelector,
    keys,
    show_toast,
)
from pigit.termui._surface import _DEFAULT_BG

from .app_theme import THEME

if TYPE_CHECKING:
    from .git.model import Branch


class BranchPanel(LazyLoadMixin, ItemSelector):
    """Branch panel with ahead/behind display and current branch highlighting."""

    CURSOR = "\u25cf"

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        content: Optional[list[str]] = None,
        *,
        on_selection_changed: Optional[Callable] = None,
    ) -> None:
        super().__init__(x, y, size, content, on_selection_changed=on_selection_changed)
        # Lazy import to avoid circular dependency
        from .git.repo import Repo

        _repo = Repo()
        self.repo_path, self.repo_conf = _repo.confirm_repo()
        self.git = _repo.bind_path(self.repo_path)
        self.branches: list[Branch] = []

    def fresh(self) -> None:
        self.branches = branches = self.git.load_branches()
        if not branches:
            self.set_content(["No branches found."])
            return
        lines = []
        for branch in branches:
            line = self._format_branch(branch)
            lines.append(line)
        self.set_content(lines)

    def get_help_entries(self) -> list[tuple[str, str]]:
        """Return help pairs for branch panel."""
        return [
            ("j/k", "Navigate"),
            ("c", "Checkout"),
        ]

    def _format_branch(self, branch: "Branch") -> str:
        """Format a branch for display."""
        return branch.name

    @bind_keys("j", keys.KEY_DOWN)
    def next(self, step: int = 1) -> None:
        super().next(step)

    @bind_keys("k", keys.KEY_UP)
    def previous(self, step: int = 1) -> None:
        super().previous(step)

    def _render_surface(self, surface) -> None:
        if not self.content:
            return
        w = surface.width
        end = min(self._r_start + self._size[1], len(self.content))

        for idx in range(self._r_start, end):
            row = idx - self._r_start
            is_cursor = idx == self.curr_no

            is_head = idx < len(self.branches) and self.branches[idx].is_head
            prefix = self.CURSOR if is_cursor else " "
            fg = THEME.accent_green if is_head else THEME.fg_primary
            text = f"{prefix} {self.content[idx]}"

            from pigit.termui.wcwidth_table import truncate_by_width, wcswidth

            if wcswidth(text) > w:
                text = truncate_by_width(text, w - 1) + "\u2026"

            surface.draw_text_rgb(row, 0, text, fg=fg, bg=_DEFAULT_BG, bold=is_cursor)

            # Draw ahead/behind indicators on the right
            if idx < len(self.branches):
                branch = self.branches[idx]
                indicators = []
                ahead = branch.ahead if branch.ahead != "?" else ""
                behind = branch.behind if branch.behind != "?" else ""
                if ahead:
                    indicators.append(f"\u2191{ahead}")
                if behind:
                    indicators.append(f"\u2193{behind}")
                indicator_str = " ".join(indicators)
                if indicator_str:
                    ind_w = wcswidth(indicator_str)
                    if ind_w < w - 4:
                        ind_x = w - ind_w
                        # ahead = green, behind = yellow
                        x = ind_x
                        if ahead:
                            a_text = f"\u2191{ahead}"
                            a_w = wcswidth(a_text)
                            surface.draw_text_rgb(
                                row, x, a_text, fg=THEME.accent_green, bg=_DEFAULT_BG
                            )
                            x += a_w + 1
                        if behind:
                            b_text = f"\u2193{behind}"
                            surface.draw_text_rgb(
                                row, x, b_text, fg=THEME.accent_yellow, bg=_DEFAULT_BG
                            )

    def on_key(self, key: str) -> None:
        if key == "c":
            if not self.branches:
                return
            local_branch = self.branches[self.curr_no]
            if local_branch.is_head:
                show_toast("Already on this branch.", duration=1.5)
                return
            err = self.git.checkout_branch(local_branch.name)
            if "error" in err:
                show_toast(f"Checkout failed: {err}", duration=3.0)
            else:
                show_toast(f"Switched to {local_branch.name}", duration=1.5)
            self.fresh()
