# -*- coding: utf-8 -*-
"""
Module: pigit/termui/scenes/repo_cd.py
Description: TTY picker for ``pigit repo cd --pick`` (no ManagedRepos import).
Author: Project Team
Date: 2026-03-27
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Callable, Optional, Sequence, Tuple

from pigit.ext.executor import WAITING

from pigit.termui.scenes.list_picker import PICK_EXIT_CTRL_C, PickerRow, run_list_picker
from pigit.termui.tty_io import tty_ok

if TYPE_CHECKING:
    from pigit.ext.executor import Executor

REPO_CD_NO_TTY_MSG = (
    "`pigit repo cd --pick`<error> needs an interactive terminal.\n"
    "Use an explicit managed repo name in scripts and CI, or run "
    "`pigit repo cd --pick` only in a real terminal.\n"
    "See `pigit repo cd -h`."
)

_REPO_CD_TERMINAL_TOO_SMALL_MSG = (
    "Terminal is too small for `pigit repo cd --pick` (need room for a fixed header, "
    "at least one list row, and a footer line). Enlarge the window or use a "
    "non-interactive repo name."
)

EMPTY_MANAGED_REPOS_MSG = "No managed repos; use `pigit repo add`."


def run_repo_cd_picker(
    rows: Sequence[PickerRow],
    executor: "Executor",
    *,
    initial_filter: str = "",
    read_char: Optional[Callable[[], str]] = None,
    write: Callable[[str], None] = sys.stdout.write,
    flush: Callable[[], None] = sys.stdout.flush,
    read_line: Callable[[str], str] = lambda p: input(p),
    pick_alt_screen: bool = False,
) -> Tuple[int, Optional[str]]:
    """
    Interactive repo directory picker; on confirm runs shell ``cd`` + ``exec $SHELL``.

    Returns:
        ``(exit_code, message)``. ``0`` with ``None`` after successful ``cd`` or user quit.
    """
    if not rows:
        return 1, EMPTY_MANAGED_REPOS_MSG
    if not tty_ok():
        return 1, REPO_CD_NO_TTY_MSG

    shell_cd = "$SHELL -c 'cd {0} && exec $SHELL'"

    def render_line(r: PickerRow) -> str:
        return f"{r.title}  {r.detail}"

    def on_confirm(r: PickerRow) -> Optional[Tuple[int, Optional[str]]]:
        path = r.ref
        assert isinstance(path, str)
        executor.exec(shell_cd.format(path), flags=WAITING)
        return 0, None

    title = (
        "pigit repo cd --pick  [j/k scroll  Enter cd  / filter  q/Esc quit  "
        "Ctrl+C abort  1-9+Enter]"
    )
    try:
        return run_list_picker(
            list(rows),
            title_line=title,
            render_line=render_line,
            on_confirm=on_confirm,
            terminal_too_small_msg=_REPO_CD_TERMINAL_TOO_SMALL_MSG,
            initial_filter=initial_filter,
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
