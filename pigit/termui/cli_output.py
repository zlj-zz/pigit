# -*- coding: utf-8 -*-
"""
Module: pigit/termui/cli_output.py
Description: Public CLI output API — replaces plenty Console.
Author: Zev
Date: 2026-05-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import palette
from ._color import ColorAdapter
from ._makrup import _resolve_color, parse_markup
from ._segment import Segment

if TYPE_CHECKING:
    RGB = tuple[int, int, int]

_adapter = ColorAdapter()


def _segments_to_ansi(segments: list[Segment]) -> str:
    """Convert a list of Segments to an ANSI escape string.

    Terminal capability downgrading is handled by ColorAdapter.
    """
    parts: list[str] = []
    for seg in segments:
        seqs: list[str] = []
        if seg.fg:
            seqs.append(_adapter.fg_sequence(seg.fg))
        if seg.bg:
            seqs.append(_adapter.bg_sequence(seg.bg))
        if seg.style_flags:
            seqs.append(_adapter.style_sequence(seg.style_flags))
        if seqs:
            prefix = "".join(s for s in seqs if s)
            parts.append(f"{prefix}{seg.text}{_adapter.reset_sequence()}")
        else:
            parts.append(seg.text)
    return "".join(parts)


class Console:
    """Lightweight CLI output terminal — replaces plenty Console."""

    def echo(
        self,
        *values: str,
        sep: str = " ",
        end: str = "\n",
        flush: bool = True,
    ) -> None:
        """Parse markup syntax and print to stdout."""
        out: list[str] = []
        for v in values:
            if "@" not in v:
                out.append(v)
            else:
                segs = parse_markup(v)
                out.append(_segments_to_ansi(segs))
        print(*out, sep=sep, end=end, flush=flush)

    def render(self, text: str) -> str:
        """Parse markup and return the ANSI string without printing."""
        if "@" not in text:
            return text
        return _segments_to_ansi(parse_markup(text))

    def echo_plain(
        self,
        *values: str,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        """Print plain text without parsing markup."""
        print(*values, sep=sep, end=end)


_console_instance: Console | None = None


def get_console() -> Console:
    """Return the global Console instance."""
    global _console_instance
    if _console_instance is None:
        _console_instance = Console()
    return _console_instance


def styled(
    text: str,
    *,
    fg: str | RGB | None = None,
    bg: str | RGB | None = None,
    bold: bool = False,
    dim: bool = False,
    italic: bool = False,
    underline: bool = False,
) -> str:
    """Return an ANSI-styled string (bypasses markup parsing).

    Args:
        text: The text to style.
        fg: Foreground color (name, HEX, or RGB tuple).
        bg: Background color (name, HEX, or RGB tuple).
        bold: Apply bold style.
        dim: Apply dim style.
        italic: Apply italic style.
        underline: Apply underline style.

    Returns:
        A string with embedded ANSI escape codes.
    """
    style_flags = 0
    if bold:
        style_flags |= palette.STYLE_BOLD
    if dim:
        style_flags |= palette.STYLE_DIM
    if italic:
        style_flags |= palette.STYLE_ITALIC
    if underline:
        style_flags |= palette.STYLE_UNDERLINE

    fg_rgb = fg if isinstance(fg, tuple) else _resolve_color(fg) if fg else None
    bg_rgb = bg if isinstance(bg, tuple) else _resolve_color(bg) if bg else None

    seg = Segment(text, fg=fg_rgb, bg=bg_rgb, style_flags=style_flags)
    return _segments_to_ansi([seg])
