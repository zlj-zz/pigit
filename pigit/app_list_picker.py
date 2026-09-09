"""
Module: pigit/app_list_picker.py
Description: Shared OptionList picker-sheet wiring for repo / worktree sheets.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from pigit.termui import Segment, bind_action, dismiss_sheet, keys
from pigit.termui.theme import selected_row_bg
from pigit.termui.mouse import MouseEvent
from pigit.termui.viewport_hit import DoubleClickTracker
from pigit.termui.widgets import OptionList

from .app_theme import THEME

_EMPTY_STATE = [
    Segment("  Nothing here", fg=THEME.fg_dim),
    Segment("press a key to act", fg=THEME.fg_muted),
]


class ListPickerSheet(OptionList):
    """Shared OptionList wiring for picker sheets (repos / worktrees).

    Provides the cursor-row selected background, ``j/k`` + filter +
    double-click activation, and ``close`` / ``toggle_mode``. Subclasses
    implement ``_row_segment_for(entry)`` and ``_handle_entry(entry)`` (dismiss
    then switch or run an action), plus their own footer / extra bindings.
    """

    # No cursor column: each sheet's row content marks the active item, so a
    # second ● would be ambiguous. The cursor row is the selected background.
    CURSOR = ""
    # Concrete sheets declare their own ``keymap_namespace`` (the runtime
    # default is the empty string when a subclass omits it).

    def __init__(
        self,
        *,
        entries: Sequence[Any],
        on_switch: Callable[[str], None],
        on_toggle_mode: Callable[[], None] | None = None,
        on_dismiss: Callable[[], None] | None = None,
        empty_state: list[Segment] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            empty_state=empty_state or _EMPTY_STATE,
            on_search_changed=self._sync_filter,
            **kwargs,
        )
        self._entries = list(entries)
        self._on_switch = on_switch
        self._on_toggle_mode = on_toggle_mode
        self._on_dismiss = on_dismiss
        self._double_click = DoubleClickTracker()
        self._row_segments: list[list[Segment]] = []
        self._rebuild_rows()

    def preferred_sheet_height(self, term_h: int) -> int:
        """Prefer up to 14 rows; host clamps to the sheet max fraction."""
        return min(14, max(6, len(self._entries) + 2))

    def set_entries(self, entries: Sequence[Any]) -> None:
        """Replace the row list (e.g. after an async meta refresh) and repaint."""
        self._entries = list(entries)
        self._rebuild_rows()

    def _rebuild_rows(self) -> None:
        self._row_segments = []
        texts: list[str] = []
        for entry in self._entries:
            segs = self._row_segment_for(entry)
            self._row_segments.append(segs)
            texts.append("".join(seg.text for seg in segs))
        self.set_source_content(texts)

    def _row_segment_for(self, entry) -> list[Segment]:
        """Segments for one sheet row (subclass implements)."""
        raise NotImplementedError

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
        sub_row: int = 0,
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        """Paint pre-built row segments; cursor uses the selected background."""
        source_idx = self.visible_to_source(idx)
        if 0 <= source_idx < len(self._row_segments):
            if not is_cursor:
                return ([], self._row_segments[source_idx], [])
            bg = selected_row_bg(THEME)
            segs = [
                Segment(s.text, fg=s.fg, bg=bg, style_flags=s.style_flags)
                for s in self._row_segments[source_idx]
            ]
            return ([], segs, [])
        return super().describe_row(idx, is_cursor, item_idx=item_idx, sub_row=sub_row)

    @bind_action("next", "j", "down", desc="Next row", tip="Navigate")
    def next(self, step: int = 1) -> None:
        self._clear_double_click()
        super().next(step)

    @bind_action("previous", "k", "up", desc="Previous row", tip="Navigate")
    def previous(self, step: int = 1) -> None:
        self._clear_double_click()
        super().previous(step)

    @bind_action("filter", "/", desc="Filter rows", tip="Filter")
    def start_filter(self) -> None:
        """Enter incremental filter mode."""
        self._clear_double_click()
        self.enter_search()

    def capture_key(self, key: str) -> bool:
        """Route keys into filter mode while active."""
        return self.search_handle_key(key)

    def _sync_filter(self) -> None:
        """Apply the search query as a substring filter over row text."""
        self.set_filter(self.search_query)

    @bind_action("confirm", keys.KEY_ENTER, desc="Activate row", tip="Switch")
    def confirm(self) -> None:
        """Activate the highlighted row."""
        self._activate_index(self.curr_no)

    @bind_action("toggle_mode", "w", desc="Toggle list mode", tip="Toggle")
    def toggle_mode(self) -> None:
        """Switch this sheet to its sibling list (repos <-> worktrees)."""
        self._clear_double_click()
        if self._on_toggle_mode is not None:
            self._on_toggle_mode()

    @bind_action("close", "@", "esc", desc="Close", tip="Close")
    def close(self) -> None:
        """Dismiss the sheet."""
        self._clear_double_click()
        if self._on_dismiss is not None:
            self._on_dismiss()
        dismiss_sheet()

    def _entry_at(self, visible_idx: int):
        """Row entry for a visible index, or ``None``."""
        if not self.content:
            return None
        if visible_idx < 0 or visible_idx >= len(self.content):
            return None
        source_idx = self.visible_to_source(visible_idx)
        if source_idx < 0 or source_idx >= len(self._entries):
            return None
        return self._entries[source_idx]

    def _activate_index(self, visible_idx: int) -> None:
        entry = self._entry_at(visible_idx)
        if entry is None:
            return
        self._handle_entry(entry)

    def _handle_entry(self, entry) -> None:
        """Dismiss the sheet and switch / run the row action (subclass)."""
        raise NotImplementedError

    def _handle_mouse_list(self, event: MouseEvent) -> bool:
        """Select on click; double-click activates (viewport_hit timing)."""
        row0 = event.row - 1
        if row0 < 0 or row0 >= self.visible_row_count:
            return False
        content_index = self._r_start + row0
        if content_index >= len(self.content):
            return False
        item_index = content_index
        if self._item_starts is not None:
            item_index, _sub = self.row_to_item(content_index)
        if item_index in self._skip_indices:
            return False
        is_double = self._double_click.is_double(item_index)
        self._select_row(item_index)
        if is_double:
            self._clear_double_click()
            self._activate_index(item_index)
        return True

    def _clear_double_click(self) -> None:
        self._double_click.clear()
