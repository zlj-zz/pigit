"""
Module: pigit/app_stash.py
Description: Stash list panel with cursor navigation.
Author: Zev
Date: 2026-05-27
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pigit.termui import (
    ActionEventType,
    bind_keys,
    palette,
    Segment,
    show_badge,
    show_toast,
)
from pigit.termui.widgets import ItemList

from .app_diff import DiffType
from .app_theme import THEME

if TYPE_CHECKING:
    from pigit.git.model import Stash
    from pigit.viewmodels.status import IStatusViewModel


class StashPanel(ItemList):
    """Stash list panel with cursor navigation."""

    CURSOR = "●"

    def __init__(
        self,
        *,
        vm: IStatusViewModel,
        id: str | None = None,
    ) -> None:
        super().__init__(
            empty_state=[
                Segment("  No stashes", fg=THEME.fg_dim),
                Segment("  Press 'z' to stash current changes", fg=THEME.fg_dim),
            ],
            id=id,
        )
        self._vm = vm
        self.stashes: list[Stash] = []

    def activate(self) -> None:
        super().activate()
        self._load_stashes()

    def _load_stashes(self) -> None:
        self.stashes = self._vm.load_stashes()
        if not self.stashes:
            self.set_content([])
            return
        self.set_content([s.msg for s in self.stashes])
        self.emit(ActionEventType.selection_changed)

    def refresh(self):
        self._load_stashes()

    @bind_keys("j")
    def next_item(self, step: int = 1) -> None:
        self.next(step)

    @bind_keys("k")
    def previous_item(self, step: int = 1) -> None:
        self.previous(step)

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
        sub_row: int = 0,
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        focused = self.is_focus_leaf
        if not self.stashes or idx >= len(self.stashes):
            return ([], None, [])
        stash = self.stashes[idx]
        cursor_prefix = self.CURSOR if is_cursor else " "
        fg = THEME.fg_primary if focused else THEME.fg_dim
        cursor_flags = palette.STYLE_BOLD if is_cursor else 0

        left = [
            Segment(cursor_prefix, fg=fg, style_flags=cursor_flags),
            Segment(" ", fg=fg),
        ]
        ref_seg = Segment(f"{stash.ref}: ", fg=THEME.fg_muted)
        msg_seg = Segment(stash.msg, fg=fg, style_flags=cursor_flags)
        main = [ref_seg, msg_seg]
        return left, main, []

    def on_key(self, key: str) -> None:
        if not self.stashes:
            return
        if key == "\r":
            stash = self.stashes[self.curr_no]
            diff_lines = self._vm.load_stash_diff(stash.ref)
            self.emit(
                ActionEventType.goto,
                target="diff",
                source=self,
                key=stash.ref,
                content=diff_lines,
                repo_path=self._vm.repo_path,
                diff_type=DiffType.STASH,
            )
            return
        if key == "p":
            stash = self.stashes[self.curr_no]
            result = self._vm.stash_pop(stash.ref)
            self._handle_result(result)
            return
        if key == "d":
            stash = self.stashes[self.curr_no]
            result = self._vm.stash_drop(stash.ref)
            self._handle_result(result)
            return

    def _handle_result(self, result) -> None:
        if result.success:
            show_badge(result.message, duration=1.0)
            self._load_stashes()
        else:
            show_toast(result.message, duration=2.0)

    def get_help_title(self) -> str:
        return "Stash"

    def get_help_entries(self) -> list[tuple[str, str]]:
        entries = [
            ("jk/↑↓", "Navigate"),
            ("↵ ", "View diff"),
            ("p", "Pop stash"),
            ("d", "Drop stash"),
        ]
        return entries

    def get_inspector_data(self):
        return None
