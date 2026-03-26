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
from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

from pigit.termui.scenes.list_picker import PICK_EXIT_CTRL_C, PickerRow, run_list_picker
from pigit.termui.tty_io import read_line_cancellable, tty_ok

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


def _execute_command_entry(
    proxy: "GitProxy",
    entry: CommandEntry,
    *,
    write: Callable[[str], None],
    flush: Callable[[], None],
) -> Optional[Tuple[int, Optional[str]]]:
    """Run one command entry; ``None`` means stay in picker (sub-prompt cancelled)."""
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
    read_char: Optional[Callable[[], str]] = None,
    write: Callable[[str], None] = sys.stdout.write,
    flush: Callable[[], None] = sys.stdout.flush,
    read_line: Callable[[str], str] = lambda p: input(p),
    pick_alt_screen: bool = False,
) -> Tuple[int, Optional[str]]:
    """
    Interactive picker over ``proxy`` commands.

    Returns:
        (exit_code, message). ``exit_code`` 0 with ``None`` means user quit with ``q``.
        ``130`` after **Ctrl+C**. Non-zero ``exit_code`` is an error; ``message`` is
        user-facing text. On successful command run, returns ``(0, output_string)``.
    """
    if not _tty_ok():
        return 1, NO_TTY_MSG

    try:
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
            return _execute_command_entry(proxy, ent, write=write, flush=flush)

        title = (
            "pigit cmd --pick  [j/k scroll  Enter run  / filter  q/Esc quit  "
            "Ctrl+C abort  1-9+Enter]"
        )
        return run_list_picker(
            rows,
            title_line=title,
            render_line=render_line,
            on_confirm=on_confirm,
            terminal_too_small_msg=_TERMINAL_TOO_SMALL_MSG,
            read_char=read_char,
            write=write,
            flush=flush,
            read_line=read_line,
            alt_screen=pick_alt_screen,
        )
    except KeyboardInterrupt:
        write("\n")
        flush()
        return PICK_EXIT_CTRL_C, None
