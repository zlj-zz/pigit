# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_picker.py
Description: Interactive picker for cmd commands (--pick functionality).
Author: Zev
Date: 2026-04-10
"""

from __future__ import annotations

import os
import shlex
import sys
from typing import Optional, TYPE_CHECKING

from pigit.termui import (
    Application,
    Column,
    Component,
    ComponentRoot,
    ExitEventLoop,
    HelpPanel,
    InputLine,
    ItemSelector,
    StatusBar,
    Popup,
    keys,
    get_renderer_strict,
)
from pigit.termui._picker import (
    PICK_EXIT_CTRL_C,
    PickerHeader,
    PickerMode,
    PickerRow,
    PickerState,
    apply_picker_filter,
    picker_terminal_ok,
)
from pigit.termui.tty_io import (
    terminal_size,
    truncate_line,
    tty_ok,
)

from ._completion import make_candidate_provider
from ._mru import load_mru
from ._picker_adapter import iter_cmd_new_entries, CmdNewEntry
from ._picker_sorter import build_context_signals, sort_picker_entries

if TYPE_CHECKING:
    from . import GitCommandNew

NO_TTY_MSG = (
    "`pigit cmd --pick`<error> needs an interactive terminal.\n"
    "Use `pigit cmd -l` for the full list or "
    "`pigit cmd -s <query>` to search.\n"
    "See `pigit cmd -h` for more options."
)

_TERMINAL_TOO_SMALL_MSG = (
    "Terminal is too small for `pigit cmd --pick` (need room for a fixed header, "
    "at least one list row, and a footer line). Enlarge the window or use "
    "`pigit cmd -l` / `pigit cmd -s <query>`."
)

# Tests can patch this
_tty_ok = tty_ok


# ---------------------------------------------------------------------------
# Picker implementation using Application facade + generic components
# ---------------------------------------------------------------------------


def run_cmd_new_picker(
    processor: Optional[GitCommandNew] = None,
    *,
    pick_alt_screen: bool = False,
    category: Optional[str] = None,
    print_only: bool = False,
) -> tuple[int, Optional[str]]:
    """Run interactive picker for cmd commands.

    Args:
        processor: GitCommandNew instance (created if None)
        pick_alt_screen: Use alternate screen buffer
        category: Optional category filter (e.g., "branch", "commit")
        print_only: Print command instead of executing

    Returns:
        (exit_code, message) tuple
    """
    if not _tty_ok():
        return 1, NO_TTY_MSG

    # Import here to avoid circular imports at module level
    from . import GitCommandNew

    processor = processor or GitCommandNew()

    # 1. Data preparation
    entries = [
        e
        for e in iter_cmd_new_entries()
        if not category or e.category.lower() == category.lower()
    ]

    mru = load_mru()
    signals = build_context_signals()
    entries = sort_picker_entries(entries, mru, signals)
    mru_set = set(mru) if mru else set()

    rows: list[PickerRow] = [
        PickerRow(title=e.name, detail=f"[{e.category}] {e.help_text}", ref=e)
        for e in entries
    ]

    def render_line(r: PickerRow) -> str:
        ent = r.ref
        assert isinstance(ent, CmdNewEntry)
        mru_mark = "⟲" if ent.name in mru_set else " "
        danger_mark = "▲" if ent.is_dangerous else " "
        return f"{mru_mark}{danger_mark} {ent.name:<15} {ent.help_text}"

    all_rendered = [render_line(r) for r in rows]

    pick_suffix = f" {category}" if category else ""
    mode_hint = "print" if print_only else "run"
    title = (
        f"pigit cmd --pick{pick_suffix}  "
        f"[j/k scroll  Enter {mode_hint}  ? preview  / filter  q/Esc quit]"
    )

    # 2. Local Application (used only inside this function)
    class _CmdPickerApp(Application):
        BINDINGS = [
            ("Q", "quit"),
            ("?", "toggle_help"),
        ]

        def __init__(self) -> None:
            super().__init__(input_takeover=True, alt=True)
            self._state = PickerState()
            self._mode = PickerMode.BROWSE
            self._number_buf: Optional[str] = None
            self._print_only = print_only
            self._processor = processor
            self._rows = rows
            self._filtered_rows = list(rows)
            self._render_line = render_line
            self._pending_entry: Optional[CmdNewEntry] = None
            self._last_needle: str = ""

        def build_root(self) -> Component:
            self._header = PickerHeader(title)
            self._list = ItemSelector(
                content=list(all_rendered),
                on_selection_changed=lambda idx: self._state.selected_idx.set(idx),
            )
            self._status = StatusBar(self._state.status_text)
            self._input = InputLine(
                prompt="/",
                visible=False,
                on_value_changed=self._on_filter_value_changed,
                on_submit=self._on_input_submit,
                on_cancel=self._on_input_cancel,
            )

            self._layout = Column(
                [self._header, self._list, self._status, self._input],
                heights=[3, "flex", 1, 0],
            )
            return self._layout

        def setup_root(self, root: ComponentRoot) -> None:
            self._loop.set_input_timeouts(0.125)
            root.show_toast(
                "j/k scroll, Enter run, / filter, ? help",
                duration=3.0,
            )
            self._help_panel = HelpPanel()
            self._help_popup = Popup(
                self._help_panel,
                session_owner=root,
                exit_key=keys.KEY_ESC,
            )
            self._state.selected_idx.subscribe(self._update_status)
            self._update_status(0)

        def after_start(self) -> None:
            _, term_rows = terminal_size()
            if not picker_terminal_ok(term_rows):
                self.quit(
                    exit_code=1,
                    result_message=_TERMINAL_TOO_SMALL_MSG,
                )

        # --- Event handling ---

        def on_key(self, key: str) -> None:
            if self._number_buf is not None:
                self._on_number_prefix(key)
                return
            if self._mode in (PickerMode.FILTER, PickerMode.PARAM_INPUT):
                if key == "ctrl c":
                    raise ExitEventLoop(
                        "quit", exit_code=PICK_EXIT_CTRL_C, result_message=None
                    )
                self._input.on_key(key)
                return
            self._on_browse(key)

        def _on_browse(self, key: str) -> None:
            if key in ("j", keys.KEY_DOWN):
                self._list.next()
            elif key in ("k", keys.KEY_UP):
                self._list.forward()
            elif key == "enter":
                self._enter_param_input()
            elif key == "/":
                self._enter_filter()
            elif key in ("q", keys.KEY_ESC):
                self.quit()
            elif key == "?":
                self._show_preview()
            elif len(key) == 1 and key.isdigit():
                self._number_buf = key
                self._echo_number(key)

        def _on_number_prefix(self, key: str) -> None:
            buf = self._number_buf
            assert buf is not None
            if key == "enter":
                self._number_buf = None
                self._clear_number_echo()
                try:
                    num = int(buf)
                except ValueError:
                    return
                if 1 <= num <= len(self._list.content):
                    self._list.curr_no = num - 1
                    self._enter_param_input()
            elif key == keys.KEY_ESC:
                self._number_buf = None
                self._clear_number_echo()
            elif len(key) == 1 and key.isdigit():
                self._number_buf = buf + key
                self._echo_number(self._number_buf)
            else:
                self._number_buf = None
                self._clear_number_echo()

        # --- Filter mode ---

        def _on_filter_value_changed(self, text: str) -> None:
            self._state.filter_text.set(text)
            self._apply_filter()

        def _enter_filter(self) -> None:
            self._mode = PickerMode.FILTER
            self._input.set_prompt("/")
            self._input.set_candidate_provider(None)
            self._input.set_visible(True)
            self._layout.set_heights([3, "flex", 1, 1])
            self.resize(self._loop.get_term_size())

        def _exit_filter(self) -> None:
            self._mode = PickerMode.BROWSE
            self._input.set_visible(False)
            self._layout.set_heights([3, "flex", 1, 0])
            self.resize(self._loop.get_term_size())

        def _apply_filter(self) -> None:
            if self._mode != PickerMode.FILTER:
                return
            needle = self._input.value
            if needle == self._last_needle:
                return
            self._last_needle = needle
            filtered = apply_picker_filter(self._rows, needle)
            self._filtered_rows = filtered
            self._list.set_content([self._format_row(r) for r in filtered])
            self._list.curr_no = 0
            self._state.selected_idx.set(0)
            self._update_status(0)

        # --- Param input mode ---

        def _enter_param_input(self) -> None:
            idx = self._list.curr_no
            if idx < 0 or idx >= len(self._filtered_rows):
                return
            row = self._filtered_rows[idx]
            ent = row.ref
            assert isinstance(ent, CmdNewEntry)

            if not ent.has_args:
                self._finish_execute(ent, "")
                return

            self._pending_entry = ent
            self._mode = PickerMode.PARAM_INPUT
            self._input.set_prompt(f"{ent.name} ")
            self._input.set_value("")
            self._input.set_candidate_provider(
                make_candidate_provider(ent.arg_completion)
            )
            self._input.set_visible(True)
            self._layout.set_heights([3, "flex", 1, 1])
            self.resize(self._loop.get_term_size())

        def _exit_param_input(self) -> None:
            self._mode = PickerMode.BROWSE
            self._pending_entry = None
            self._input.set_candidate_provider(None)
            self._input.clear()
            self._input.set_prompt("/")
            self._input.set_visible(False)
            self._layout.set_heights([3, "flex", 1, 0])
            self.resize(self._loop.get_term_size())

        def _on_input_submit(self, value: str) -> None:
            if self._mode == PickerMode.FILTER:
                self._exit_filter()
            elif self._mode == PickerMode.PARAM_INPUT:
                assert self._pending_entry is not None
                self._finish_execute(self._pending_entry, value)

        def _on_input_cancel(self) -> None:
            if self._mode == PickerMode.FILTER:
                self._exit_filter()
                self._input.clear()
            elif self._mode == PickerMode.PARAM_INPUT:
                self._exit_param_input()

        # --- Business logic ---

        def _finish_execute(self, ent: CmdNewEntry, extra_raw: str) -> None:
            extra_args = shlex.split(extra_raw.strip()) if extra_raw.strip() else []
            if self._print_only:
                cmd_parts = ["pigit", "cmd", ent.name, *extra_args]
                result = " ".join(shlex.quote(p) for p in cmd_parts)
                raise ExitEventLoop("done", exit_code=0, result_message=result)
            exit_code, output = self._processor.execute(ent.name, extra_args)
            raise ExitEventLoop("done", exit_code=exit_code, result_message=output)

        def _format_row(self, row: PickerRow) -> str:
            return self._render_line(row)

        def _update_status(self, idx: int) -> None:
            n = len(self._list.content)
            vp = self._list.visible_row_count
            if n > vp:
                lo = self._list.viewport_start + 1
                hi = min(self._list.viewport_start + vp, n)
                text = f"-- rows {lo}-{hi} of {n} --"
            else:
                text = f"-- {n} row(s) --"
            self._state.status_text.set(text)

        def _show_preview(self) -> None:
            idx = self._list.curr_no
            if idx < 0 or idx >= len(self._filtered_rows):
                return
            ent = self._filtered_rows[idx].ref
            assert isinstance(ent, CmdNewEntry)
            preview = self._processor.preview(ent.name, [])
            if preview[1]:
                self._status.set_text(f"preview: {preview[1]}")

        def _echo_number(self, buf: str) -> None:
            renderer = get_renderer_strict()
            cols, _ = terminal_size()
            line = truncate_line(f"# {buf} — Enter to confirm", cols)
            renderer.draw_absolute_row(1, line)

        def _clear_number_echo(self) -> None:
            renderer = get_renderer_strict()
            cols, _ = terminal_size()
            renderer.draw_absolute_row(1, " " * cols)

        def quit(
            self, exit_code: int = 0, result_message: Optional[str] = None
        ) -> None:
            raise ExitEventLoop(
                "quit", exit_code=exit_code, result_message=result_message
            )

        def toggle_help(self) -> None:
            self._help_popup.toggle()

    # 3. Launch
    exit_code, message = _CmdPickerApp().run_with_result()

    # print_only output is handled after Application exits so it lands on
    # the main screen, not inside the alternate screen buffer.
    if print_only and message is not None:
        widget_output = os.environ.get("PIGIT_WIDGET_OUTPUT")
        if widget_output:
            try:
                with open(widget_output, "w", encoding="utf-8") as f:
                    f.write(message + "\n")
            except OSError as exc:
                return 1, f"Failed to write widget output: {exc}"
        else:
            sys.stdout.write(message + "\n")
            sys.stdout.flush()
        return 0, None

    return exit_code, message
