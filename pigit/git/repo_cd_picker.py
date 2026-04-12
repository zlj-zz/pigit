# -*- coding: utf-8 -*-
"""
Module: pigit/git/repo_cd_picker.py
Description: TTY picker for ``pigit repo cd --pick`` (executor / shell cd live in git, not termui).
Author: Zev
Date: 2026-03-29
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Optional, Sequence

from pigit.ext.executor import WAITING

from pigit.termui.component_list_picker import (
    PICK_EXIT_CTRL_C,
    PickerRow,
    SearchableListPicker,
)
from pigit.termui.picker_event_loop import PickerAppEventLoop
from pigit.termui.picker_layout import picker_terminal_ok
from pigit.termui.tty_io import terminal_size, tty_ok
from pigit.termui.tui_input_bridge import TermuiInputBridge

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


class RepoCdPickerLoop(PickerAppEventLoop):
    """Drives :class:`SearchableListPicker` for managed-repo ``cd`` selection."""

    BINDINGS = [
        ("Q", "binding_quit_picker"),
    ]

    def __init__(
        self,
        rows: Sequence[PickerRow],
        executor: "Executor",
        *,
        initial_filter: str = "",
        pick_alt_screen: bool = False,
    ) -> None:
        self._terminal_too_small_msg = _REPO_CD_TERMINAL_TOO_SMALL_MSG

        def render_line(r: PickerRow) -> str:
            return f"{r.title}  {r.detail}"

        def on_confirm(r: PickerRow) -> Optional[tuple[int, Optional[str]]]:
            path = r.ref
            assert isinstance(path, str)
            # Return path via result_message; executor will run after Session exits
            # to ensure terminal is properly restored (alt screen, cursor, termios)
            return 0, path

        title = (
            "pigit repo cd --pick  [j/k scroll  Enter cd  / filter  q/Esc quit  "
            "Ctrl+C abort  1-9+Enter]"
        )
        picker = SearchableListPicker(
            list(rows),
            title_line=title,
            render_line=render_line,
            on_confirm=on_confirm,
            terminal_too_small_msg=self._terminal_too_small_msg,
            initial_filter=initial_filter,
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


def run_repo_cd_picker(
    rows: Sequence[PickerRow],
    executor: "Executor",
    *,
    initial_filter: str = "",
    pick_alt_screen: bool = False,
) -> tuple[int, Optional[str]]:
    """
    Interactive repo directory picker; on confirm runs shell ``cd`` + ``exec $SHELL``.

    Requires a real TTY (same gate as :func:`tty_ok`).

    Returns:
        ``(exit_code, message)``. ``0`` with ``None`` after successful ``cd`` or user quit.
    """
    if not rows:
        return 1, EMPTY_MANAGED_REPOS_MSG
    if not tty_ok():
        return 1, REPO_CD_NO_TTY_MSG

    try:
        loop = RepoCdPickerLoop(
            rows,
            executor,
            initial_filter=initial_filter,
            pick_alt_screen=pick_alt_screen,
        )
        exit_code, result = loop.run_with_result()
        # After Session exits, execute shell command if a repo was selected.
        # This ensures terminal is properly restored (alt screen, cursor, termios)
        # before spawning the interactive shell.
        if exit_code == 0 and result is not None:
            shell_cd = "$SHELL -c 'cd {0} && exec $SHELL'"
            executor.exec(shell_cd.format(result), flags=WAITING)
        return exit_code, None
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()
        return PICK_EXIT_CTRL_C, None
