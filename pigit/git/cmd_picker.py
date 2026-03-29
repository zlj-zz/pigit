# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmd_picker.py
Description: Built-in TTY command picker for ``pigit cmd --pick`` (j/k, filter, execute).
Author: Project Team
Date: 2026-03-22
"""

from __future__ import annotations

import shlex
import sys
from typing import List, Optional, Tuple, TYPE_CHECKING

from pigit.termui.component_list_picker import PICK_EXIT_CTRL_C, PickerRow, SearchableListPicker
from pigit.termui.picker_event_loop import PickerAppEventLoop
from pigit.termui.picker_layout import picker_terminal_ok
from pigit.termui.tty_io import read_line_cancellable, terminal_size, tty_ok
from pigit.termui.tui_input_bridge import TermuiInputBridge

from .cmd_catalog import CommandEntry, iter_command_entries

if TYPE_CHECKING:
    from .cmd_proxy import GitProxy

NO_TTY_MSG = (
    "`pigit cmd --pick`<error> needs an interactive terminal.\n"
    "Use `pigit cmd -l` for the full table or "
    "`pigit cmd -s <query>` / `pigit cmd --search <query>` to filter.\n"
    "See `pigit cmd -h` for more options."
)

_TERMINAL_TOO_SMALL_MSG = (
    "Terminal is too small for `pigit cmd --pick` (need room for a fixed header, "
    "at least one list row, and a footer line). Enlarge the window or use "
    "`pigit cmd -l` / `pigit cmd -s <query>`."
)

# Tests patch ``pigit.git.cmd_picker._tty_ok``.
_tty_ok = tty_ok


class CommandPickerLoop(PickerAppEventLoop):
    """Drives :class:`SearchableListPicker` over command catalog entries."""

    BINDINGS = [
        ("Q", "binding_quit_picker"),
    ]

    def __init__(
        self,
        proxy: "GitProxy",
        *,
        pick_alt_screen: bool = False,
    ) -> None:
        self._terminal_too_small_msg = _TERMINAL_TOO_SMALL_MSG

        all_entries = iter_command_entries(proxy.cmds, proxy.extra_cmd_keys)
        rows: List[PickerRow] = [
            PickerRow(
                title=e.name,
                detail=f"{e.help_text} {e.command_repr}".strip(),
                ref=e,
            )
            for e in all_entries
        ]

        def render_line(r: PickerRow) -> str:
            ent = r.ref
            assert isinstance(ent, CommandEntry)
            return proxy.generate_help_by_key(ent.name, use_color=False)

        def on_confirm(r: PickerRow) -> Optional[Tuple[int, Optional[str]]]:
            ent = r.ref
            assert isinstance(ent, CommandEntry)
            return _execute_command_entry(proxy, ent)

        title = (
            "pigit cmd --pick  [j/k scroll  Enter run  / filter  q/Esc quit  "
            "Ctrl+C abort  1-9+Enter]"
        )
        picker = SearchableListPicker(
            rows,
            title_line=title,
            render_line=render_line,
            on_confirm=on_confirm,
            terminal_too_small_msg=self._terminal_too_small_msg,
        )
        super().__init__(
            picker,
            input_takeover=True,
            input_handle=TermuiInputBridge(),
            alt=pick_alt_screen,
        )
        self.set_input_timeouts(0.125)
        picker.bind_event_loop(self)

    def binding_quit_picker(self) -> None:
        self.quit("quit", exit_code=0, result_message=None)

    def after_start(self) -> None:
        _, rows = terminal_size()
        if not picker_terminal_ok(rows):
            self.quit(
                "terminal",
                exit_code=1,
                result_message=self._terminal_too_small_msg,
            )


def _execute_command_entry(
    proxy: "GitProxy",
    entry: CommandEntry,
) -> Optional[Tuple[int, Optional[str]]]:
    """Run one command entry; ``None`` means stay in picker (sub-prompt cancelled)."""
    write = sys.stdout.write
    flush = sys.stdout.flush

    spec = proxy.cmds.get(entry.name) or {}
    cmd = spec.get("command")
    if cmd is None:
        return 1, "`Invalid command entry (no command).`<error>"

    if isinstance(cmd, str):
        if not entry.has_arguments:
            return 0, proxy.do(entry.name, [])
        write(
            "\nAppend arguments after the short command "
            "(empty line = run without extra args). Esc cancels.\n"
            f"pigit cmd {entry.name} "
        )
        flush()
        extra_raw = read_line_cancellable(write=write, flush=flush, prompt="")
        if extra_raw is None:
            return None
        extra_args = shlex.split(extra_raw.strip()) if extra_raw.strip() else []
        return 0, proxy.do(entry.name, extra_args)

    write("\nThis entry runs a Python handler (not a shell git line). Esc cancels.\n")
    flush()
    extra_raw = read_line_cancellable(write=write, flush=flush, prompt="args> ")
    if extra_raw is None:
        return None
    extra_args = shlex.split(extra_raw.strip()) if extra_raw.strip() else []
    return 0, proxy.do(entry.name, extra_args)


def run_command_picker(
    proxy: "GitProxy",
    *,
    pick_alt_screen: bool = False,
) -> Tuple[int, Optional[str]]:
    """
    Interactive picker over ``proxy`` commands (requires a real TTY).

    Returns:
        (exit_code, message). ``exit_code`` 0 with ``None`` means user quit with ``q``.
        ``130`` after **Ctrl+C**. Non-zero ``exit_code`` is an error; ``message`` is
        user-facing text. On successful command run, returns ``(0, output_string)``.
    """
    if not _tty_ok():
        return 1, NO_TTY_MSG

    try:
        loop = CommandPickerLoop(proxy, pick_alt_screen=pick_alt_screen)
        return loop.run_with_result()
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()
        return PICK_EXIT_CTRL_C, None
