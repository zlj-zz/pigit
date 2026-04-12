# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_picker.py
Description: Interactive picker for cmd_new commands (--pick functionality).
Author: Zev
Date: 2026-04-10
"""

from __future__ import annotations

import shlex
import sys
from typing import Optional, TYPE_CHECKING

from pigit.termui.component_list_picker import (
    PICK_EXIT_CTRL_C,
    PickerRow,
    SearchableListPicker,
)
from pigit.termui.picker_event_loop import PickerAppEventLoop
from pigit.termui.picker_layout import picker_terminal_ok
from pigit.termui.tty_io import read_line_cancellable, terminal_size, tty_ok
from pigit.termui.tui_input_bridge import TermuiInputBridge

from ._picker_adapter import iter_cmd_new_entries, CmdNewEntry

if TYPE_CHECKING:
    from . import GitCommandNew

NO_TTY_MSG = (
    "`pigit cmd_new --pick`<error> needs an interactive terminal.\n"
    "Use `pigit cmd_new -l` for the full list or "
    "`pigit cmd_new -s <query>` to search.\n"
    "See `pigit cmd_new -h` for more options."
)

_TERMINAL_TOO_SMALL_MSG = (
    "Terminal is too small for `pigit cmd_new --pick` (need room for a fixed header, "
    "at least one list row, and a footer line). Enlarge the window or use "
    "`pigit cmd_new -l` / `pigit cmd_new -s <query>`."
)

# Tests can patch this
_tty_ok = tty_ok


class CmdNewPickerLoop(PickerAppEventLoop):
    """Event loop for cmd_new command picker."""

    BINDINGS = [
        ("Q", "binding_quit_picker"),
    ]

    def __init__(
        self,
        processor: GitCommandNew,
        *,
        pick_alt_screen: bool = False,
        category: Optional[str] = None,
    ) -> None:
        """Initialize picker loop.

        Args:
            processor: GitCommandNew instance for executing commands
            pick_alt_screen: Use alternate screen buffer
            category: Optional category filter (e.g., "branch", "commit")
        """
        self._terminal_too_small_msg = _TERMINAL_TOO_SMALL_MSG

        entries = list(iter_cmd_new_entries())

        # Filter by category if specified
        if category:
            category_lower = category.lower()
            entries = [e for e in entries if e.category.lower() == category_lower]

        rows: list[PickerRow] = [
            PickerRow(
                title=e.name,
                detail=f"[{e.category}] {e.help_text}",
                ref=e,
            )
            for e in entries
        ]

        def render_line(r: PickerRow) -> str:
            ent = r.ref
            assert isinstance(ent, CmdNewEntry)
            prefix = "⚠️ " if ent.is_dangerous else "  "
            return f"{prefix} {ent.name:<15} {ent.help_text}"

        def on_confirm(r: PickerRow) -> Optional[tuple[int, Optional[str]]]:
            ent = r.ref
            assert isinstance(ent, CmdNewEntry)
            return self._execute_command(ent, processor)

        # Build title with optional category filter
        pick_suffix = f" {category}" if category else ""
        title = (
            f"pigit cmd_new --pick{pick_suffix}  [j/k scroll  Enter run  / filter  "
            f"q/Esc quit  Ctrl+C abort  1-9+Enter]"
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
        """Quit picker with Q key."""
        self.quit("quit", exit_code=0, result_message=None)

    def after_start(self) -> None:
        """Check terminal size after starting."""
        _, rows = terminal_size()
        if not picker_terminal_ok(rows):
            self.quit(
                "terminal",
                exit_code=1,
                result_message=self._terminal_too_small_msg,
            )

    def _execute_command(
        self,
        entry: CmdNewEntry,
        processor: GitCommandNew,
    ) -> Optional[tuple[int, Optional[str]]]:
        """Execute selected command with optional arguments.

        Args:
            entry: Selected command entry
            processor: GitCommandNew instance

        Returns:
            (exit_code, output) tuple, or None if cancelled
        """
        write = sys.stdout.write
        flush = sys.stdout.flush

        if entry.has_args:
            write(f"\nArguments for `{entry.name}` (empty = none, Esc = cancel):\n")
            flush()
            extra_raw = read_line_cancellable(
                write=write, flush=flush, prompt=f"{entry.name} "
            )
            if extra_raw is None:
                return None
            extra_args = shlex.split(extra_raw.strip()) if extra_raw.strip() else []
        else:
            extra_args = []

        exit_code, output = processor.execute(entry.name, extra_args)
        return exit_code, output


def run_cmd_new_picker(
    processor: Optional[GitCommandNew] = None,
    *,
    pick_alt_screen: bool = False,
    category: Optional[str] = None,
) -> tuple[int, Optional[str]]:
    """Run interactive picker for cmd_new commands.

    Args:
        processor: GitCommandNew instance (created if None)
        pick_alt_screen: Use alternate screen buffer
        category: Optional category filter (e.g., "branch", "commit")

    Returns:
        (exit_code, message) tuple
    """
    if not _tty_ok():
        return 1, NO_TTY_MSG

    # Import here to avoid circular imports at module level
    from . import GitCommandNew

    processor = processor or GitCommandNew()

    try:
        loop = CmdNewPickerLoop(
            processor, pick_alt_screen=pick_alt_screen, category=category
        )
        return loop.run_with_result()
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()
        return PICK_EXIT_CTRL_C, None
