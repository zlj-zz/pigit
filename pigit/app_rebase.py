"""
Module: pigit/app_rebase.py
Description: Interactive rebase todo-list panel (edit actions and order, then execute).
Author: Zev
Date: 2026-08-14
"""

from __future__ import annotations

import os
import shlex
import tempfile
from dataclasses import dataclass
from typing import TYPE_CHECKING
from collections.abc import Callable

from pigit.app_theme import THEME
from pigit.termui import (
    Segment,
    exec_external,
    keys,
    palette,
    request_render,
    show_badge,
    show_toast,
)
from pigit.termui.widgets import AlertDialog, ItemList
from pigit.termui.wcwidth_table import wcswidth

if TYPE_CHECKING:
    from pigit.git.api import GitApi

# Ordered git sequence commands; squash/fixup merge into the previous line.
_ACTION_BY_KEY: dict[str, str] = {
    "p": "pick",
    "s": "squash",
    "f": "fixup",
    "d": "drop",
    "r": "reword",
    "e": "edit",
}
_ACTION_FG = {
    "pick": THEME.fg_primary,
    "squash": THEME.fg_info,
    "fixup": THEME.fg_info,
    "drop": THEME.fg_danger,
    "reword": THEME.fg_warning,
    "edit": THEME.fg_warning,
}
# Actions that merge into the previous commit and therefore cannot be first.
_MERGE_ACTIONS = ("squash", "fixup")

# One-line key hint rendered at the bottom of the panel (the sheet covers the
# global footer, so the panel owns its own hint). Styled like the footer:
# key bright + bold, description dim.
_HINT_PAIRS = [
    ("p", "pick"),
    ("s", "squash"),
    ("f", "fixup"),
    ("d", "drop"),
    ("r", "reword"),
    ("e", "edit"),
    ("J/K", "move"),
    ("Enter", "confirm"),
    ("Esc", "cancel"),
]


@dataclass
class _TodoItem:
    """One editable line of the rebase todo list."""

    sha: str
    subject: str
    action: str = "pick"


class RebasePanel(ItemList):
    """Sheet overlay for editing the interactive-rebase todo list."""

    CURSOR = "●"

    def __init__(
        self,
        git: "GitApi",
        base: str,
        on_done: Callable[[], None],
    ) -> None:
        super().__init__()
        self._git = git
        self._base = base
        self._on_done = on_done
        self._items: list[_TodoItem] = []
        self._alert = AlertDialog(inner_width=50, on_result=lambda _: None)

    def activate(self) -> None:
        """Load the range and validate; dismiss on any guard failure."""
        if self._git.is_rebase_in_progress() or self._git.is_merge_in_progress():
            show_toast("A rebase or merge is already in progress", duration=2.0)
            self._on_done()
            return
        commits = self._git.list_commits_in_range(self._base)
        if not commits:
            show_toast("No commits to rebase", duration=2.0)
            self._on_done()
            return
        if any(c.is_merge for c in commits):
            show_toast("Range contains merges (unsupported)", duration=2.0)
            self._on_done()
            return
        self._items = [_TodoItem(c.sha, c.msg) for c in commits]
        self.set_content([self._display(item) for item in self._items])

    def _display(self, item: _TodoItem) -> str:
        return f"{item.action} {item.sha[:8]} {item.subject}"

    def on_key(self, key: str) -> None:
        if key == keys.KEY_ESC:
            self._on_done()
            return
        if key == keys.KEY_ENTER:
            self._confirm()
            return
        if key in (keys.KEY_DOWN, "j"):
            self.next()
            return
        if key in (keys.KEY_UP, "k"):
            self.previous()
            return
        if key in _ACTION_BY_KEY:
            self._set_action(key)
            return
        if key == "J":
            self._move_up()
            return
        if key == "K":
            self._move_down()

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
        sub_row: int = 0,
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        item = self._items[idx]
        left = [
            Segment(self.CURSOR if is_cursor else " ", fg=THEME.fg_primary),
            Segment(" ", fg=THEME.fg_primary),
            Segment(item.action.ljust(7), fg=_ACTION_FG[item.action]),
        ]
        fg = THEME.fg_primary if is_cursor else THEME.fg_dim
        main = [Segment(f"{item.sha[:8]}  {item.subject}", fg=fg)]
        return left, main, []

    def get_help_entries(self) -> list[tuple[str, str]]:
        return [
            ("jk/↑↓", "Navigate"),
            ("p/s/f/d/r/e", "pick/squash/fixup/drop/reword/edit"),
            ("J/K", "Move up/down"),
            ("Enter", "Confirm and execute"),
            ("Esc", "Cancel"),
        ]

    def _render_surface(self, surface) -> None:
        """Render the list, reserving the last row for the key hint."""
        height = self._size[1]
        if height <= 1:
            super()._render_surface(surface)
            return
        width, _ = self._size
        self._size = (width, height - 1)
        try:
            super()._render_surface(surface)
        finally:
            self._size = (width, height)
        self._draw_hint(surface, height - 1)

    def _draw_hint(self, surface, row: int) -> None:
        """Draw the key hints in the footer style (key bold, description dim)."""
        x = 0
        for key, desc in _HINT_PAIRS:
            pair_w = wcswidth(key) + 1 + wcswidth(desc)
            if x + pair_w > surface.width:
                if surface.width - x > 1:
                    surface.draw_text_rgb(row, x, "…", fg=THEME.fg_muted)
                break
            key_w = wcswidth(key)
            surface.draw_text_rgb(
                row, x, key, fg=THEME.fg_primary, style_flags=palette.STYLE_BOLD
            )
            x += key_w
            rest = f" {desc}  "
            surface.draw_text_rgb(row, x, rest, fg=THEME.fg_muted)
            x += wcswidth(rest)

    # ── editing ──

    def _set_action(self, key: str) -> None:
        idx = self.curr_no
        action = _ACTION_BY_KEY[key]
        if action in _MERGE_ACTIONS and idx == 0:
            show_toast("Cannot squash/fixup the first commit", duration=1.5)
            return
        self._items[idx].action = action
        request_render()

    def _move_up(self) -> None:
        idx = self.curr_no
        if idx == 0:
            return
        if idx == 1 and self._items[idx].action in _MERGE_ACTIONS:
            show_toast("Cannot move squash/fixup to the top", duration=1.5)
            return
        self._items[idx], self._items[idx - 1] = self._items[idx - 1], self._items[idx]
        self.curr_no = idx - 1

    def _move_down(self) -> None:
        idx = self.curr_no
        if idx >= len(self._items) - 1:
            return
        if idx == 0 and self._items[idx + 1].action in _MERGE_ACTIONS:
            show_toast("Cannot move squash/fixup to the top", duration=1.5)
            return
        self._items[idx], self._items[idx + 1] = self._items[idx + 1], self._items[idx]
        self.curr_no = idx + 1

    # ── execute ──

    def _confirm(self) -> None:
        n = len(self._items)
        self._alert.alert(
            f"Rewrite {n} commits? This rewrites history.",
            self._on_confirm_result,
        )

    def _on_confirm_result(self, confirmed: bool) -> None:
        if confirmed:
            self._execute()

    def _execute(self) -> None:
        todo_lines = [f"{item.action} {item.sha} {item.subject}" for item in self._items]
        tmp = tempfile.NamedTemporaryFile("w", suffix=".todo", delete=False)
        tmp.write("\n".join(todo_lines))
        tmp.close()
        try:
            result = exec_external(
                ["git", "rebase", "-i", self._base],
                cwd=self._git.path,
                env={**os.environ, "GIT_SEQUENCE_EDITOR": f"cp {shlex.quote(tmp.name)}"},
            )
        finally:
            os.unlink(tmp.name)

        if self._git.is_rebase_in_progress():
            show_toast("Rebase paused. Resolve, then rb.c / rb.a / rb.s", duration=3.0)
        elif result.returncode != 0:
            show_toast("Rebase failed", duration=2.0)
        else:
            show_badge("Rebase complete", duration=1.5)
        self._on_done()
