# -*- coding: utf-8 -*-
"""
Module: pigit/interactive/list_picker.py
Description: Generic full-screen list picker (j/k, filter, confirm) built on tty primitives.
Author: Project Team
Date: 2026-03-23
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from .layout import (
    filter_input_line,
    footer_status_line,
    picker_terminal_ok,
    picker_viewport,
)
from .tty_primitives import (
    lone_esc_or_consume_sequence,
    read_char_raw,
    terminal_size,
    truncate_line,
)

PICK_EXIT_CTRL_C = 130


@dataclass(frozen=True)
class PickerRow:
    """One selectable row: ``title`` + ``detail`` participate in substring filter."""

    title: str
    detail: str = ""
    ref: object = None


def apply_picker_filter(rows: Sequence[PickerRow], needle: str) -> List[PickerRow]:
    """Case-insensitive substring match on ``title`` and ``detail`` (like ``cmd --pick``)."""

    if not needle.strip():
        return list(rows)
    q = needle.lower()
    return [r for r in rows if q in r.title.lower() or q in (r.detail or "").lower()]


def _write_picker_header(
    write: Callable[[str], None], title_line: str, cols: int
) -> None:
    write("\033[2J\033[H")
    sep = "=" * min(72, cols)
    write(sep + "\n")
    write(truncate_line(title_line, cols) + "\n")
    write(sep + "\n")


def _pin_row(write: Callable[[str], None], row: int, text: str) -> None:
    """Output specified text to the target terminal row and clear its original content."""
    write(f"\033[{row};1H\033[K{text}")


def _pin_bottom_rows(
    write: Callable[[str], None],
    flush: Callable[[], None],
    term_rows: int,
    cols: int,
    foot: str,
    needle: str,
    has_filter: bool,
    filter_editing: bool,
) -> None:
    status_row = term_rows - 1
    input_row = term_rows
    _pin_row(
        write,
        status_row,
        footer_status_line(foot, needle, has_filter, filter_editing, cols),
    )
    _pin_row(
        write,
        input_row,
        filter_input_line(needle, cols) if filter_editing else "",
    )
    flush()


def run_list_picker(
    all_rows: Sequence[PickerRow],
    *,
    title_line: str,
    render_line: Callable[[PickerRow], str],
    on_confirm: Callable[[PickerRow], Optional[Tuple[int, Optional[str]]]],
    terminal_too_small_msg: str,
    initial_filter: str = "",
    read_char: Callable[[], str] = read_char_raw,
    write: Callable[[str], None] = sys.stdout.write,
    flush: Callable[[], None] = sys.stdout.flush,
    read_line: Callable[[str], str] = lambda p: input(p),
) -> Tuple[int, Optional[str]]:
    """
    Interactive full-screen list picker.

    Returns:
        ``(exit_code, message)``. ``0`` with ``None`` means user quit with ``q``/Esc.
        ``130`` after **Ctrl+C**. Non-zero ``exit_code`` is an error.
    """
    needle = initial_filter
    filtered = apply_picker_filter(list(all_rows), needle)
    index = 0
    scroll_offset = 0
    filter_editing = False

    def _sync_scroll(viewport: int) -> None:
        nonlocal scroll_offset
        if not filtered:
            scroll_offset = 0
            return
        n = len(filtered)
        if n <= viewport:
            scroll_offset = 0
            return
        if index < scroll_offset:
            scroll_offset = index
        elif index >= scroll_offset + viewport:
            scroll_offset = index - viewport + 1
        max_scroll = n - viewport
        scroll_offset = max(0, min(scroll_offset, max_scroll))

    def redraw() -> Optional[str]:
        nonlocal index
        cols, term_rows = terminal_size()
        has_filter = bool(needle) or filter_editing
        if not picker_terminal_ok(term_rows):
            return terminal_too_small_msg

        vp = picker_viewport(term_rows)

        if not filtered:
            _write_picker_header(write, title_line, cols)
            msg = (
                "No matches. Press / to edit filter, q or Esc to quit, "
                "Ctrl+C to abort."
            )
            for _ in range(vp):
                write(truncate_line(msg, cols) + "\n")
                msg = ""
            _pin_bottom_rows(
                write, flush, term_rows, cols, "--", needle, has_filter, filter_editing
            )
            return None

        if index >= len(filtered):
            index = len(filtered) - 1
        if index < 0:
            index = 0

        _sync_scroll(vp)

        _write_picker_header(write, title_line, cols)

        for row in range(vp):
            li = scroll_offset + row
            if li >= len(filtered):
                write("\n")
                continue
            ent = filtered[li]
            prefix = "> " if li == index else "  "
            raw = render_line(ent).lstrip()
            body = truncate_line(raw, cols - len(prefix))
            write(prefix + body + "\n")

        n = len(filtered)
        if n > vp:
            lo = scroll_offset + 1
            hi = min(scroll_offset + vp, n)
            foot = f"-- rows {lo}-{hi} of {n} (j/k scroll) --"
        else:
            foot = f"-- {n} row(s) --"
        _pin_bottom_rows(
            write, flush, term_rows, cols, foot, needle, has_filter, filter_editing
        )
        return None

    def _echo_number_at_bottom(number_buf: str) -> None:
        cols, term_rows = terminal_size()
        line = truncate_line(f"# {number_buf} — Enter to confirm", cols)
        write(f"\033[{term_rows};1H\033[K{line}")
        flush()

    def _clear_bottom_status_row() -> None:
        _, term_rows = terminal_size()
        write(f"\033[{term_rows};1H\033[K")
        flush()

    def _filter_edit_loop(saved_needle: str) -> Optional[Tuple[int, Optional[str]]]:
        nonlocal needle, filtered, index, filter_editing, scroll_offset
        filter_editing = True
        while filter_editing:
            filtered = apply_picker_filter(list(all_rows), needle)
            if filtered:
                if index >= len(filtered):
                    index = len(filtered) - 1
                if index < 0:
                    index = 0
            else:
                index = 0
            layout_err = redraw()
            if layout_err:
                return 1, layout_err
            try:
                ec = read_char()
            except (OSError, AttributeError, ValueError):
                filter_editing = False
                write(
                    "\nSingle-key input is not available in filter mode; "
                    "press Enter to finish editing.\n"
                )
                flush()
                needle = saved_needle
                filtered = apply_picker_filter(list(all_rows), needle)
                return None
            except KeyboardInterrupt:
                write("\n")
                flush()
                return PICK_EXIT_CTRL_C, None
            if ec in ("\r", "\n"):
                filter_editing = False
                continue
            if ec == "\x1b":
                if lone_esc_or_consume_sequence():
                    needle = saved_needle
                    filtered = apply_picker_filter(list(all_rows), needle)
                    filter_editing = False
                continue
            if ec in ("\x7f", "\x08"):
                if needle:
                    needle = needle[:-1]
                continue
            if len(ec) == 1 and ord(ec) >= 32:
                needle += ec
        scroll_offset = 0
        return None

    _, initial_rows = terminal_size()
    if not picker_terminal_ok(initial_rows):
        return 1, terminal_too_small_msg

    while True:
        layout_err = redraw()
        if layout_err:
            return 1, layout_err

        try:
            ch = read_char()
        except (OSError, AttributeError, ValueError):
            write(
                "\nSingle-key input is not available; "
                "enter a line: [number] to select, q to quit, /text to filter.\n"
            )
            flush()
            try:
                line = read_line("pick> ").strip()
            except KeyboardInterrupt:
                write("\n")
                flush()
                return PICK_EXIT_CTRL_C, None
            if line.lower() in ("q", "quit"):
                return 0, None
            if line.startswith("/"):
                needle = line[1:]
                filtered = apply_picker_filter(list(all_rows), needle)
                index = 0
                scroll_offset = 0
                continue
            if line.isdigit():
                n = int(line)
                if 1 <= n <= len(filtered):
                    out = on_confirm(filtered[n - 1])
                    if out is not None:
                        return out
                else:
                    write(f"Invalid index {n} (1-{len(filtered)}).\n")
                    flush()
                continue
            write("Unrecognized input; try a number, /keyword, or q.\n")
            flush()
            continue

        if ch in ("\r", "\n"):
            if not filtered:
                continue
            out = on_confirm(filtered[index])
            if out is not None:
                return out
            continue

        if ch in ("j", "J"):
            if filtered:
                index = (index + 1) % len(filtered)
            continue

        if ch in ("k", "K"):
            if filtered:
                index = (index - 1) % len(filtered)
            continue

        if ch in ("q", "Q"):
            return 0, None

        if ch == "\x1b":
            if lone_esc_or_consume_sequence():
                return 0, None
            continue

        if ch == "/":
            saved_needle = needle
            edit_out = _filter_edit_loop(saved_needle)
            if edit_out is not None:
                return edit_out
            continue

        if ch.isdigit():
            buf = ch
            _echo_number_at_bottom(buf)
            while True:
                try:
                    c = read_char()
                except KeyboardInterrupt:
                    _clear_bottom_status_row()
                    write("\n")
                    flush()
                    return PICK_EXIT_CTRL_C, None
                if c in ("\r", "\n"):
                    break
                if c == "\x1b":
                    if lone_esc_or_consume_sequence():
                        _clear_bottom_status_row()
                        break
                    continue
                if c.isdigit():
                    buf += c
                    _echo_number_at_bottom(buf)
                else:
                    _clear_bottom_status_row()
                    break
            try:
                num = int(buf)
            except ValueError:
                _clear_bottom_status_row()
                continue
            if filtered and 1 <= num <= len(filtered):
                _clear_bottom_status_row()
                out = on_confirm(filtered[num - 1])
                if out is not None:
                    return out
            else:
                _clear_bottom_status_row()
            continue
