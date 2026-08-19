"""
Module: pigit/app_log_ref.py
Description: Sheet to pick which ref the Commit panel logs.
Author: Zev
Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Callable

from pigit.termui import bind_action, keys, palette, Segment
from pigit.termui.widgets import ItemList

from .app_theme import THEME


class LogRefSheet(ItemList):
    """Pick a git ref to show in the Commit log (no checkout)."""

    CURSOR = "●"
    keymap_namespace = "log_ref"

    def __init__(
        self,
        names: list[str],
        current_ref: str,
        on_pick: Callable[[str], None],
        on_done: Callable[[], None],
    ) -> None:
        super().__init__(
            on_selection_changed=None,
            on_search_changed=self._sync_filter,
        )
        self._all = list(names)
        self._current_ref = current_ref
        self._on_pick = on_pick
        self._on_done = on_done

    def _sync_filter(self) -> None:
        """Apply the current search query to the ref list."""
        self.set_source_items(self._all, text_of=lambda name: name)
        self.set_filter(self.search_query)

    def activate(self) -> None:
        super().activate()
        self._sync_filter()
        if self._current_ref in self.content:
            self.curr_no = self.content.index(self._current_ref)
        else:
            self.curr_no = 0
        self._scroll_into_view()

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
        sub_row: int = 0,
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        """Cursor glyph, ref name, and a ``current`` tag on the active log_ref."""
        name = self.content[idx] if idx < len(self.content) else ""
        cursor = self.CURSOR if is_cursor else " "
        name_fg = THEME.fg_primary if is_cursor else THEME.fg_dim
        left = [Segment(f"{cursor} ", fg=THEME.fg_primary)]
        main = [
            Segment(
                name,
                fg=name_fg,
                style_flags=palette.STYLE_BOLD if is_cursor else 0,
            )
        ]
        right: list[Segment] = []
        if name == self._current_ref:
            right = [Segment("current", fg=THEME.fg_success)]
        return left, main, right

    def capture_key(self, key: str) -> bool:
        # Enter confirms the selection even while a filter query is active,
        # instead of only deactivating the filter (search_handle_key consumes Enter).
        if key == keys.KEY_ENTER:
            self.confirm()
            return True
        if self.search_handle_key(key):
            return True
        return self.search_active

    @bind_action("next", "j", "down", desc="Navigate refs", tip="Navigate")
    def next(self, step: int = 1) -> None:
        super().next(step)

    @bind_action("previous", "k", "up", desc="Navigate refs", tip="Navigate")
    def previous(self, step: int = 1) -> None:
        super().previous(step)

    @bind_action("search", "/", desc="Filter refs")
    def search(self) -> None:
        self.enter_search()

    @bind_action("confirm", "enter", desc="Show this log")
    def confirm(self) -> None:
        if not self.content:
            return
        self._on_pick(self.content[self.curr_no])
        self._on_done()

    @bind_action("close", "esc", desc="Close")
    def close(self) -> None:
        self._on_done()
