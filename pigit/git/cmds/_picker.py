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

from pigit.termui.component_list_picker import (
    PICK_EXIT_CTRL_C,
    PickerRow,
    SearchableListPicker,
)
from pigit.termui.picker_event_loop import PickerAppEventLoop
from pigit.termui.picker_layout import picker_terminal_ok
from pigit.termui.tty_io import read_line_cancellable, terminal_size, tty_ok
from pigit.termui.tui_input_bridge import TermuiInputBridge
from pigit.context import Context

from ._picker_adapter import iter_cmd_new_entries, CmdNewEntry
from ._mru import load_mru

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


def _build_context_signals() -> dict[str, bool]:
    """Detect working-tree context signals from current repo.

    Returns:
        Dict with keys has_unstaged, has_staged, has_conflict
    """
    signals = {
        "has_unstaged": False,
        "has_staged": False,
        "has_conflict": False,
    }
    ctx = Context.try_current()
    if ctx is None:
        return signals
    try:
        files = ctx.repo.load_status()
    except Exception:
        return signals

    for f in files:
        if f.has_unstaged_change or not f.tracked:
            signals["has_unstaged"] = True
        if f.has_staged_change:
            signals["has_staged"] = True
        if f.has_merged_conflicts:
            signals["has_conflict"] = True
    return signals


def _context_score(entry: CmdNewEntry, signals: dict[str, bool]) -> int:
    """Compute context-aware priority score for an entry.

    Args:
        entry: Command entry
        signals: Context signals from _build_context_signals

    Returns:
        Priority score (higher = more relevant)
    """
    cat = entry.category.lower()
    score = 0
    if signals.get("has_unstaged") and cat == "index":
        score += 100
    if signals.get("has_staged") and cat == "commit":
        score += 100
    if signals.get("has_conflict") and cat in ("conflict", "merge"):
        score += 100
    return score


def _sort_picker_entries(
    entries: list[CmdNewEntry],
    mru: list[str],
    signals: dict[str, bool],
) -> list[CmdNewEntry]:
    """Sort entries by MRU, context relevance, then name.

    Args:
        entries: Command entries
        mru: MRU command names in order
        signals: Context signals

    Returns:
        Sorted entries
    """
    mru_index = {name: idx for idx, name in enumerate(mru)}

    def sort_key(e: CmdNewEntry) -> tuple[int, int, str]:
        return (
            mru_index.get(e.name, 999),
            -_context_score(e, signals),
            e.name,
        )

    return sorted(entries, key=sort_key)


class CmdNewPickerLoop(PickerAppEventLoop):
    """Event loop for cmd command picker."""

    BINDINGS = [
        ("Q", "binding_quit_picker"),
    ]

    def __init__(
        self,
        processor: GitCommandNew,
        *,
        pick_alt_screen: bool = False,
        category: Optional[str] = None,
        print_only: bool = False,
    ) -> None:
        """Initialize picker loop.

        Args:
            processor: GitCommandNew instance for executing commands
            pick_alt_screen: Use alternate screen buffer
            category: Optional category filter (e.g., "branch", "commit")
            print_only: Print command instead of executing
        """
        self._terminal_too_small_msg = _TERMINAL_TOO_SMALL_MSG
        self._print_only = print_only

        entries = list(iter_cmd_new_entries())

        # Filter by category if specified
        if category:
            category_lower = category.lower()
            entries = [e for e in entries if e.category.lower() == category_lower]

        # Load MRU and context signals, then sort entries
        mru = load_mru()
        signals = _build_context_signals()
        entries = _sort_picker_entries(entries, mru, signals)
        mru_set = set(mru) if mru else set()

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
            mru_mark = "⟲" if mru_set and ent.name in mru_set else " "
            danger_mark = "▲" if ent.is_dangerous else " "
            return f"{mru_mark}{danger_mark} {ent.name:<15} {ent.help_text}"

        def on_confirm(r: PickerRow) -> Optional[tuple[int, Optional[str]]]:
            ent = r.ref
            assert isinstance(ent, CmdNewEntry)
            return self._execute_command(ent, processor)

        # Build title with optional category filter
        pick_suffix = f" {category}" if category else ""
        mode_hint = "print" if print_only else "run"
        title = (
            f"pigit cmd --pick{pick_suffix}  [j/k scroll  Enter {mode_hint}  / filter  "
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

        # We are committed to running the command; leave the alternate screen
        # so output appears on the normal terminal.
        if self._alt:
            write("\033[?1049l\033[?25h")
            flush()

        if self._print_only:
            cmd_parts = ["pigit", "cmd", entry.name, *extra_args]
            output_line = " ".join(shlex.quote(p) for p in cmd_parts) + "\n"
            widget_output = os.environ.get("PIGIT_WIDGET_OUTPUT")
            if widget_output:
                try:
                    with open(widget_output, "w", encoding="utf-8") as f:
                        f.write(output_line)
                except OSError as exc:
                    write(f"\nFailed to write widget output: {exc}\n")
                    flush()
                    return 1, None
            else:
                write(output_line)
                flush()
            return 0, None

        exit_code, output = processor.execute(entry.name, extra_args)
        return exit_code, output


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

    try:
        loop = CmdNewPickerLoop(
            processor,
            pick_alt_screen=pick_alt_screen,
            category=category,
            print_only=print_only,
        )
        return loop.run_with_result()
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()
        return PICK_EXIT_CTRL_C, None
