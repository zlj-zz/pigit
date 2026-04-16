# -*- coding: utf-8 -*-
"""
Module: pigit/termui/component_list_picker.py
Description: Full-screen searchable list picker as a Component driven by AppEventLoop.
Author: Zev
Date: 2026-03-29
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence, TYPE_CHECKING

from pigit.termui.components import Component
from pigit.termui.picker_layout import (
    filter_input_line,
    footer_status_line,
    picker_terminal_ok,
    picker_viewport,
)
from pigit.termui.tty_io import terminal_size, truncate_line

if TYPE_CHECKING:
    from pigit.termui.event_loop import AppEventLoop
    from pigit.termui.surface import Surface

PICK_EXIT_CTRL_C = 130


@dataclass(frozen=True)
class PickerRow:
    """One selectable row: ``title`` + ``detail`` participate in substring filter."""

    title: str
    detail: str = ""
    ref: object = None


def apply_picker_filter(rows: Sequence[PickerRow], needle: str) -> list[PickerRow]:
    """Case-insensitive substring match on ``title`` and ``detail``."""

    if not needle.strip():
        return list(rows)
    q = needle.lower()
    return [r for r in rows if q in r.title.lower() or q in (r.detail or "").lower()]


class SearchableListPicker(Component):
    """
    Root component for ``cmd --pick`` / ``repo cd --pick``: filter, scroll, confirm.

    Must be used under :class:`~pigit.termui.picker_event_loop.PickerAppEventLoop`
    with :meth:`~SearchableListPicker.bind_event_loop` called after construction.
    """

    NAME = "searchable_list_picker"

    def __init__(
        self,
        all_rows: Sequence[PickerRow],
        *,
        title_line: str,
        render_line: Callable[[PickerRow], str],
        on_confirm: Callable[[PickerRow], Optional[tuple[int, Optional[str]]]],
        terminal_too_small_msg: str,
        initial_filter: str = "",
        on_preview: Optional[Callable[[PickerRow], Optional[str]]] = None,
    ) -> None:
        super().__init__()
        self._all_rows = list(all_rows)
        self._title_line = title_line
        self._render_line = render_line
        self._on_confirm = on_confirm
        self._on_preview = on_preview
        self._terminal_too_small_msg = terminal_too_small_msg

        self._needle = initial_filter
        self._filtered: list[PickerRow] = apply_picker_filter(
            self._all_rows, self._needle
        )
        self._index = 0
        self._scroll_offset = 0
        self._filter_editing = False
        self._number_prefix: Optional[str] = None
        self._saved_needle_for_filter = ""
        self._preview_text: Optional[str] = None

        self._loop: Optional["AppEventLoop"] = None

    def bind_event_loop(self, loop: "AppEventLoop") -> None:
        """Attach the owning loop for :meth:`quit_with_result`."""

        self._loop = loop

    def fresh(self) -> None:
        return

    def _sync_scroll(self, viewport: int) -> None:
        if not self._filtered:
            self._scroll_offset = 0
            return
        n = len(self._filtered)
        if n <= viewport:
            self._scroll_offset = 0
            return
        if self._index < self._scroll_offset:
            self._scroll_offset = self._index
        elif self._index >= self._scroll_offset + viewport:
            self._scroll_offset = self._index - viewport + 1
        max_scroll = n - viewport
        self._scroll_offset = max(0, min(self._scroll_offset, max_scroll))

    def _quit(self, exit_code: int, message: Optional[str]) -> None:
        assert self._loop is not None
        self._loop.quit("picker", exit_code=exit_code, result_message=message)

    def _render_surface(self, surface: "Surface") -> None:
        cols, term_rows = self._size
        has_filter = bool(self._needle) or self._filter_editing
        if not picker_terminal_ok(term_rows):
            self._quit(1, self._terminal_too_small_msg)
            return

        vp = picker_viewport(term_rows)
        filtered = self._filtered

        # Header
        sep = "=" * min(72, cols)
        surface.draw_text(0, 0, sep)
        surface.draw_text(1, 0, truncate_line(self._title_line, cols))
        surface.draw_text(2, 0, sep)

        if not filtered:
            msg = (
                "No matches. Press / to edit filter, q or Esc to quit, "
                "Ctrl+C to abort."
            )
            for row in range(3, 3 + vp):
                surface.draw_row(row, msg if row == 3 else "")
        else:
            if self._index >= len(filtered):
                self._index = len(filtered) - 1
            if self._index < 0:
                self._index = 0

            self._sync_scroll(vp)
            for row in range(vp):
                li = self._scroll_offset + row
                if li >= len(filtered):
                    surface.draw_row(3 + row, "")
                    continue
                ent = filtered[li]
                prefix = "> " if li == self._index else "  "
                raw = self._render_line(ent).lstrip()
                body = truncate_line(raw, cols - len(prefix))
                surface.draw_row(3 + row, prefix + body)

        # Footer
        n = len(filtered)
        if n > vp:
            lo = self._scroll_offset + 1
            hi = min(self._scroll_offset + vp, n)
            foot = f"-- rows {lo}-{hi} of {n} (j/k scroll) --"
        else:
            foot = f"-- {n} row(s) --"

        status_row = term_rows - 2
        input_row = term_rows - 1
        if self._preview_text:
            surface.draw_row(status_row, truncate_line(self._preview_text, cols))
            self._preview_text = None
        else:
            surface.draw_row(
                status_row,
                footer_status_line(foot, self._needle, has_filter, self._filter_editing, cols),
            )
        if self._filter_editing:
            surface.draw_row(input_row, filter_input_line(self._needle, cols))

    def _echo_number_at_bottom(self, number_buf: str) -> None:
        r = self._renderer
        assert r is not None
        cols, term_rows = terminal_size()
        line = truncate_line(f"# {number_buf} — Enter to confirm", cols)
        r.draw_absolute_row(term_rows, line)
        r.flush()

    def _clear_bottom_status_row(self) -> None:
        r = self._renderer
        assert r is not None
        _, term_rows = terminal_size()
        r.draw_absolute_row(term_rows, "")
        r.flush()

    def on_key(self, key: str) -> None:
        if self._number_prefix is not None:
            self._on_key_number_prefix(key)
            return
        if self._filter_editing:
            self._on_key_filter_edit(key)
            return
        self._on_key_browse(key)

    def _on_key_browse(self, key: str) -> None:
        r = self._renderer
        assert r is not None

        if key == "enter":
            if not self._filtered:
                return
            out = self._on_confirm(self._filtered[self._index])
            if out is not None:
                self._quit(out[0], out[1])
            return

        if key in ("j", "down"):
            if self._filtered:
                self._index = (self._index + 1) % len(self._filtered)
            return

        if key in ("k", "up"):
            if self._filtered:
                self._index = (self._index - 1) % len(self._filtered)
            return

        if key == "q":
            self._quit(0, None)
            return

        if key == "esc":
            self._quit(0, None)
            return

        if key == "/":
            self._saved_needle_for_filter = self._needle
            self._filter_editing = True
            return

        if key == "ctrl c":
            r.write("\n")
            r.flush()
            self._quit(PICK_EXIT_CTRL_C, None)
            return

        if key == "?":
            if not self._filtered or self._on_preview is None:
                return
            preview_text = self._on_preview(self._filtered[self._index])
            if preview_text:
                self._preview_text = f"preview: {preview_text}"
            return

        if len(key) == 1 and key.isdigit():
            self._number_prefix = key
            self._echo_number_at_bottom(self._number_prefix)
            return

    def _on_key_filter_edit(self, key: str) -> None:
        r = self._renderer
        assert r is not None

        if key == "enter":
            self._filter_editing = False
            self._scroll_offset = 0
            self._filtered = apply_picker_filter(self._all_rows, self._needle)
            self._reconcile_index()
            return

        if key == "esc":
            self._needle = self._saved_needle_for_filter
            self._filtered = apply_picker_filter(self._all_rows, self._needle)
            self._filter_editing = False
            self._scroll_offset = 0
            self._reconcile_index()
            return

        if key == "backspace":
            if self._needle:
                self._needle = self._needle[:-1]
            self._filtered = apply_picker_filter(self._all_rows, self._needle)
            self._reconcile_index()
            return

        if key == "ctrl c":
            r.write("\n")
            r.flush()
            self._quit(PICK_EXIT_CTRL_C, None)
            return

        if len(key) == 1 and key.isprintable() and ord(key) >= 32:
            self._needle += key
            self._filtered = apply_picker_filter(self._all_rows, self._needle)
            self._reconcile_index()
            return

    def _reconcile_index(self) -> None:
        if self._filtered:
            if self._index >= len(self._filtered):
                self._index = len(self._filtered) - 1
            if self._index < 0:
                self._index = 0
        else:
            self._index = 0

    def _on_key_number_prefix(self, key: str) -> None:
        r = self._renderer
        assert r is not None
        buf = self._number_prefix
        assert buf is not None

        if key == "enter":
            self._number_prefix = None
            self._clear_bottom_status_row()
            try:
                num = int(buf)
            except ValueError:
                return
            if self._filtered and 1 <= num <= len(self._filtered):
                out = self._on_confirm(self._filtered[num - 1])
                if out is not None:
                    self._quit(out[0], out[1])
                return
            return

        if key == "esc":
            self._number_prefix = None
            self._clear_bottom_status_row()
            return

        if key == "ctrl c":
            self._number_prefix = None
            self._clear_bottom_status_row()
            r.write("\n")
            r.flush()
            self._quit(PICK_EXIT_CTRL_C, None)
            return

        if len(key) == 1 and key.isdigit():
            buf = buf + key
            self._number_prefix = buf
            self._echo_number_at_bottom(buf)
            return

        self._number_prefix = None
        self._clear_bottom_status_row()
