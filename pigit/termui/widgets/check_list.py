"""
Module: pigit/termui/widgets/check_list.py
Description: Multi-select list widget with checkbox prefix.
Author: Zev
Date: 2026-05-16
"""

from __future__ import annotations

from .. import palette
from ..reactive import Signal
from .._segment import Segment
from .item_list import ItemList


class CheckList(ItemList):
    """Multi-select list with checkbox prefix."""

    CURSOR: str = ""
    CHECKED: str = "✓"
    UNCHECKED: str = "·"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._checked_sig: Signal[set[int]] = Signal(set())
        self._checked_unsub = self._checked_sig.subscribe(
            self._on_checked_change
        )

    def _on_checked_change(self, _: set[int]) -> None:
        """Handler for _checked_sig changes."""
        self._request_render()

    @property
    def _checked(self) -> set[int]:
        return self._checked_sig.value

    @_checked.setter
    def _checked(self, value: set[int]) -> None:
        self._checked_sig.set(value)

    def destroy(self) -> None:
        self._checked_unsub()
        super().destroy()

    # --- public API ---

    def toggle(self, idx: int | None = None) -> None:
        """Toggle checkbox at ``idx`` (defaults to current cursor)."""
        if idx is None:
            idx = self.curr_no
        checked = set(self._checked)
        if idx is None or idx in checked:
            checked.discard(idx)
        else:
            checked.add(idx)
        self._checked = checked

    def select_all(self) -> None:
        self._checked = set(range(len(self.content)))

    def select_none(self) -> None:
        self._checked = set()

    def get_selected(self) -> set[int]:
        return set(self._checked)

    def set_content(self, content: list[str]) -> None:
        """Override to clamp checked indices on content change."""

        super().set_content(content)
        self._checked = {i for i in self._checked if i < len(content)}

    # --- rendering ---

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
        sub_row: int = 0,
    ) -> tuple[
        list[Segment],
        list[Segment] | None,
        list[Segment],
    ]:
        """Render compact checkbox with bg_active for selected rows."""
        is_checked = idx in self._checked
        if is_checked:
            bg = palette.BG_ACTIVE
        elif is_cursor:
            bg = palette.BG_HOVER
        else:
            bg = palette.DEFAULT_BG
        marker = (
            Segment(
                self.CHECKED, fg=palette.GREEN, bg=bg, style_flags=palette.STYLE_BOLD
            )
            if is_checked
            else Segment(self.UNCHECKED, fg=palette.DIM, bg=bg)
        )
        text = Segment(self.content[idx], fg=palette.DEFAULT_FG, bg=bg)
        return ([marker, Segment(" ", fg=palette.DEFAULT_FG, bg=bg)], [text], [])
