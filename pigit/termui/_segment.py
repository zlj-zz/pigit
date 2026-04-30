# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_segment.py
Description: Styled text fragment for terminal rendering.
Author: Zev
Date: 2026-04-30
"""

from __future__ import annotations

from typing import Optional

from . import palette


_STYLE_NAMES: dict[int, str] = {
    palette.STYLE_BOLD: "bold",
    palette.STYLE_DIM: "dim",
    palette.STYLE_ITALIC: "italic",
    palette.STYLE_UNDERLINE: "underline",
    palette.STYLE_REVERSE: "reverse",
}


class Segment:
    """A styled text fragment for terminal rendering.

    ``fg`` and ``bg`` are ``None`` when no color is specified.
    The caller (e.g. ``draw_text_rgb``) decides how to interpret ``None``.
    """

    __slots__ = ("text", "fg", "bg", "style_flags")

    def __init__(
        self,
        text: str,
        fg: Optional[tuple[int, int, int]] = None,
        bg: Optional[tuple[int, int, int]] = None,
        style_flags: int = 0,
    ) -> None:
        self.text = text
        self.fg = fg
        self.bg = bg
        self.style_flags = style_flags

    @classmethod
    def bold(cls, text: str, fg: Optional[tuple[int, int, int]] = None) -> "Segment":
        return cls(text, fg=fg, style_flags=palette.STYLE_BOLD)

    @classmethod
    def dim(
        cls, text: str, fg: Optional[tuple[int, int, int]] = palette.DEFAULT_FG_DIM
    ) -> "Segment":
        return cls(text, fg=fg, style_flags=palette.STYLE_DIM)

    @classmethod
    def reverse(
        cls,
        text: str,
        fg: Optional[tuple[int, int, int]] = None,
        bg: Optional[tuple[int, int, int]] = None,
    ) -> "Segment":
        return cls(text, fg=fg, bg=bg, style_flags=palette.STYLE_REVERSE)

    def has_style(self, flag: int) -> bool:
        return bool(self.style_flags & flag)

    def __repr__(self) -> str:
        names = [name for bit, name in _STYLE_NAMES.items() if self.style_flags & bit]
        style = "|".join(names) if names else "normal"
        return f"Segment({self.text!r}, fg={self.fg}, bg={self.bg}, {style})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Segment):
            return NotImplemented
        return (
            self.text == other.text
            and self.fg == other.fg
            and self.bg == other.bg
            and self.style_flags == other.style_flags
        )

    def __hash__(self) -> int:
        return hash((self.text, self.fg, self.bg, self.style_flags))
