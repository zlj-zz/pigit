# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_picker_prompt.py
Description: Argument prompter for picker with cursor management.
Author: Zev
Date: 2026-04-15
"""

from typing import Callable, Optional

from pigit.termui.tty_io import read_line_cancellable, read_line_with_completion


def _dim_hint(text: str) -> str:
    """Dim hint text via ANSI SGR."""
    return f"\033[2m{text}\033[0m"


class ArgumentPrompter:
    """Prompts for command arguments and manages cursor visibility."""

    def __init__(
        self,
        renderer,
        write: Callable[[str], None],
        flush: Callable[[], None],
    ):
        """Initialize ArgumentPrompter.

        Args:
            renderer: Renderer with show_cursor/hide_cursor methods.
            write: Output writer.
            flush: Output flusher.
        """
        self._renderer = renderer
        self._write = write
        self._flush = flush

    def prompt(
        self,
        entry_name: str,
        candidate_provider: Optional[Callable[[str], list[str]]],
    ) -> Optional[str]:
        """Prompt for arguments and return user input.

        Args:
            entry_name: Name of the command being prompted for.
            candidate_provider: Optional callback for Tab completion candidates.

        Returns:
            The entered line, or None if cancelled.
        """
        self._renderer.show_cursor()
        self._flush()
        self._write(f"\nArguments for `{entry_name}` (empty = none, Esc = cancel):\n")
        self._flush()

        if candidate_provider:
            raw = read_line_with_completion(
                write=self._write,
                flush=self._flush,
                prompt=f"{entry_name} ",
                candidate_provider=candidate_provider,
                hint_styler=_dim_hint,
            )
        else:
            raw = read_line_cancellable(
                write=self._write, flush=self._flush, prompt=f"{entry_name} "
            )

        self._renderer.hide_cursor()
        self._flush()
        return raw
