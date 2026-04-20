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
    Component,
    ComponentRoot,
    ExitEventLoop,
    HelpPanel,
    Popup,
    keys,
)
from pigit.termui._component_layouts import Column
from pigit.termui._component_widgets import (
    InputLine,
    ItemSelector,
    StatusBar,
)
from pigit.termui._picker import (
    PICK_EXIT_CTRL_C,
    PickerAppMixin,
    PickerHeader,
    PickerMode,
    PickerRow,
    PickerState,
)
from pigit.termui._renderer_context import get_renderer_strict
from pigit.termui.picker_layout import picker_terminal_ok
from pigit.termui.tty_io import (
    read_line_cancellable,
    read_line_with_completion,
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
        e for e in iter_cmd_new_entries()
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
    class _CmdPickerApp(Application, PickerAppMixin):
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
                on_value_changed=lambda text: self._state.filter_text.set(text),
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
            if self._mode == PickerMode.FILTER:
                self._on_filter(key)
                return
            self._on_browse(key)

        def _on_browse(self, key: str) -> None:
            if key in ("j", keys.KEY_DOWN):
                self._list.next()
            elif key in ("k", keys.KEY_UP):
                self._list.forward()  # forward = scroll up (index decreases)
            elif key == "enter":
                self._execute_selected()
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
                    self._execute_selected()
            elif key == keys.KEY_ESC:
                self._number_buf = None
                self._clear_number_echo()
            elif len(key) == 1 and key.isdigit():
                self._number_buf = buf + key
                self._echo_number(self._number_buf)
            else:
                self._number_buf = None
                self._clear_number_echo()

        # --- Business logic ---

        def _execute_selected(self) -> None:
            idx = self._list.curr_no
            if idx < 0 or idx >= len(self._filtered_rows):
                return
            ent = self._filtered_rows[idx].ref
            assert isinstance(ent, CmdNewEntry)

            extra_args: list[str] = []
            if ent.has_args:
                renderer = get_renderer_strict()
                cols, rows = terminal_size()
                # Clear bottom two rows for prompt
                renderer.draw_absolute_row(rows - 2, " " * cols)
                renderer.draw_absolute_row(rows - 1, " " * cols)
                # Build prompt text and write once
                prompt_text = (
                    f"Arguments for `{ent.name}` (empty = none, Esc = cancel):"
                )
                renderer.move_cursor(rows - 1, 1)
                renderer.write(prompt_text)
                renderer.move_cursor(rows, 1)
                renderer.flush()
                renderer.show_cursor()

                provider = make_candidate_provider(ent.arg_completion)
                if provider:
                    extra_raw = read_line_with_completion(
                        write=sys.stdout.write,
                        flush=sys.stdout.flush,
                        prompt=f"{ent.name} ",
                        candidate_provider=provider,
                        hint_styler=lambda t: f"\033[2m{t}\033[0m",
                    )
                else:
                    extra_raw = read_line_cancellable(
                        write=sys.stdout.write,
                        flush=sys.stdout.flush,
                        prompt=f"{ent.name} ",
                    )

                renderer.hide_cursor()
                if extra_raw is None:
                    # User cancelled — wipe bottom rows and re-render TUI
                    renderer.draw_absolute_row(rows - 2, " " * cols)
                    renderer.draw_absolute_row(rows - 1, " " * cols)
                    self._loop.render()
                    return
                extra_args = (
                    shlex.split(extra_raw.strip()) if extra_raw.strip() else []
                )

            if self._print_only:
                cmd_parts = ["pigit", "cmd", ent.name, *extra_args]
                result = " ".join(shlex.quote(p) for p in cmd_parts)
                raise ExitEventLoop(
                    "done", exit_code=0, result_message=result
                )
            exit_code, output = self._processor.execute(ent.name, extra_args)
            raise ExitEventLoop(
                "done", exit_code=exit_code, result_message=output
            )

        def _format_row(self, row: PickerRow) -> str:
            return self._render_line(row)

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
