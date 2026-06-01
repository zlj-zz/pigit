"""
Module: pigit/app_recent_actions.py
Description: RecentActionsPanel for browsing and reversing session history.
Author: Zev
Date: 2026-06-01
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Callable

from pigit.ext.utils import relative_time
from pigit.termui import palette, Segment, keys
from pigit.termui.widgets import ItemList

if TYPE_CHECKING:
    from pigit.git.local_git import LocalGit
    from pigit.session_history import SessionHistory, HistoryRecord


class RecentActionsPanel(ItemList):
    """Sheet overlay for browsing and reversing session history records."""

    CURSOR = "●"

    def __init__(
        self,
        history: SessionHistory,
        git: LocalGit,
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

    def on_key(self, key: str) -> None:
        if key == keys.KEY_ESC:
            self._on_done()
            return
        if key == keys.KEY_ENTER and self._records:
            target_idx = self.curr_no
            result = self._history.reverse_to(target_idx, self._git)
            if result.success:
                from pigit.termui import show_badge

                show_badge(result.message, duration=1.5)
            else:
                from pigit.termui import show_toast

                show_toast(result.message, duration=2.0)
            self._on_done()
            return
        # Delegate navigation to parent ItemList
        if key == keys.KEY_DOWN or key == "j":
            self.next()
            return
        if key == keys.KEY_UP or key == "k":
            self.previous()
            return

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
        sub_row: int = 0,
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        record = self._records[idx]
        cursor_seg = Segment(self.CURSOR if is_cursor else " ", fg=palette.DEFAULT_FG)
        left = [cursor_seg, Segment(" ")]

        main = [Segment(record.description, fg=palette.DEFAULT_FG)]

        right_text = f"{relative_time(int(record.timestamp))}  {record.panel_hint}"
        right = [Segment(right_text, fg=palette.DEFAULT_FG_DIM)]

        return left, main, right

    def get_help_entries(self) -> list[tuple[str, str]]:
        return [
            ("jk/↑↓", "Navigate"),
            ("Enter", "Reverse to here"),
            ("Esc", "Close"),
        ]
