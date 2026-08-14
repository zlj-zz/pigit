"""
Module: pigit/app_recent_actions.py
Description: RecentActionsPanel for browsing and reversing session history.
Author: Zev
Date: 2026-06-01
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Callable

from pigit.app_theme import THEME
from pigit.ext.utils import relative_time
from pigit.termui import FeedbackKind, Segment, bind_action, show_badge, show_toast
from pigit.termui.widgets import ItemList

if TYPE_CHECKING:
    from pigit.git.api import GitApi
    from pigit.session_history import SessionHistory, HistoryRecord


class RecentActionsPanel(ItemList):
    """Sheet overlay for browsing and reversing session history records."""

    CURSOR = "●"
    keymap_namespace = "recent"

    def __init__(
        self,
        history: SessionHistory,
        git: GitApi,
        on_done: Callable[[], None],
    ) -> None:
        super().__init__(on_selection_changed=None)
        self._history = history
        self._git = git
        self._on_done = on_done
        self._records: list[HistoryRecord] = []

    def activate(self) -> None:
        """Load and display history records."""
        self._refresh()

    def _refresh(self) -> None:
        self._records = self._history.peek(20)
        self.set_content([r.description for r in self._records])

    @bind_action("next", "j", "down", desc="Navigate history list", tip="Navigate")
    def next(self, step: int = 1) -> None:
        super().next(step)

    @bind_action("previous", "k", "up", desc="Navigate history list", tip="Navigate")
    def previous(self, step: int = 1) -> None:
        super().previous(step)

    @bind_action("reverse", "enter", desc="Reverse to selected action", tip="Reverse")
    def reverse(self) -> None:
        if not self._records:
            return
        target_idx = self.curr_no
        result = self._history.reverse_to(target_idx, self._git)
        if result.success:
            show_badge(result.message, duration=1.5, kind=FeedbackKind.SUCCESS)
        else:
            show_toast(result.message, duration=2.0, kind=FeedbackKind.ERROR)
        self._on_done()

    @bind_action("close", "esc", desc="Close panel", tip="Close")
    def close(self) -> None:
        self._on_done()

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
        sub_row: int = 0,
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        record = self._records[idx]
        cursor_seg = Segment(self.CURSOR if is_cursor else " ", fg=THEME.fg_primary)
        left = [cursor_seg, Segment(" ")]

        main = [Segment(record.description, fg=THEME.fg_primary)]

        right_text = f"{relative_time(int(record.timestamp))}  {record.panel_hint}"
        right = [Segment(right_text, fg=THEME.fg_dim)]

        return left, main, right
