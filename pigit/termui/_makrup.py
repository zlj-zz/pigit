# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_makrup.py
Description: CLI markup parser for @color(content) syntax.
Author: Zev
Date: 2026-05-19
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

from . import palette
from ._segment import Segment

if TYPE_CHECKING:
    RGB = tuple[int, int, int]

# ── Named color mapping ──
_NAME_TO_RGB: dict[str, RGB] = {
    # Reuse termui palette
    "cyan": palette.CYAN,
    "yellow": palette.YELLOW,
    "green": palette.GREEN,
    "red": palette.RED,
    # Legacy plenty colors
    "sky_blue": palette.SKY_BLUE,
    "tomato": palette.TOMATO,
    "khaki": palette.KHAKI,
    "pink": palette.PINK,
    "violet_red": palette.VIOLET_RED,
    "pale_green": palette.PALE_GREEN,
}

# Style flag mapping
_FLAG_MAP: dict[str, int] = {
    "bold": palette.STYLE_BOLD,
    "dim": palette.STYLE_DIM,
    "italic": palette.STYLE_ITALIC,
    "underline": palette.STYLE_UNDERLINE,
    "reverse": palette.STYLE_REVERSE,
}

_TAG_START_CHARS: set[str] = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_#"
)


def _resolve_color(name: str) -> RGB | None:
    """Resolve a color name or HEX string to an RGB tuple.

    Args:
        name: Color name (e.g. "red", "sky_blue") or HEX (e.g. "#ff6347").

    Returns:
        RGB tuple or None if the name cannot be resolved.
    """
    if not name:
        return None
    if name.startswith("#") and len(name) == 7:
        try:
            return (
                int(name[1:3], 16),
                int(name[3:5], 16),
                int(name[5:7], 16),
            )
        except ValueError:
            return None
    return _NAME_TO_RGB.get(name)


def _parse_attrs(attr_str: str) -> tuple[RGB | None, RGB | None, int]:
    """Parse an attribute string into (fg, bg, flags).

    Does not assume the first part is a color.

    Args:
        attr_str: Comma-separated attributes like "bold,red,bg=blue".

    Returns:
        A tuple of (foreground_rgb, background_rgb, style_flags).
    """
    parts = attr_str.split(",")
    fg: RGB | None = None
    bg: RGB | None = None
    flags = 0
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p.startswith("bg="):
            bg = _resolve_color(p[3:])
        elif p in _FLAG_MAP:
            flags |= _FLAG_MAP[p]
        elif fg is None and (rgb := _resolve_color(p)) is not None:
            fg = rgb
        else:
            warnings.warn(f"Unknown markup attribute: {p!r}", stacklevel=3)
    return fg, bg, flags


def _parse_tag(text: str, start: int) -> tuple[str, int]:
    """Parse a @attrs(content) tag starting at ``start`` (the '@' position).

    Uses a depth counter to correctly handle nested parentheses and
    content that contains ')'.

    Args:
        text: The full text string.
        start: Index of the '@' character.

    Returns:
        A tuple of (attrs_str, content_end_pos) where content_end_pos
        points to the closing ')'.
    """
    i = start + 1
    attrs_start = i
    while i < len(text) and text[i] != "(":
        i += 1
    attrs = text[attrs_start:i]
    i += 1  # skip '('
    depth = 1
    while i < len(text) and depth > 0:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
        i += 1
    content_end = i - 1  # position of the outer closing ')'
    return attrs, content_end


def parse_markup(text: str) -> list[Segment]:
    """Recursively parse @color(content) markup into a list of Segments.

    Args:
        text: Raw text potentially containing markup tags.

    Returns:
        A list of styled text fragments.
    """
    segments: list[Segment] = []
    pos = 0
    while pos < len(text):
        at = text.find("@", pos)
        if at == -1:
            break
        # Escaped literal @: "@@" → "@"
        if at + 1 < len(text) and text[at + 1] == "@":
            if at > pos:
                segments.append(Segment(text[pos:at]))
            segments.append(Segment("@"))
            pos = at + 2
            continue
        # Distinguish markup @ from literal @ (e.g. email addresses)
        if at + 1 >= len(text) or text[at + 1] not in _TAG_START_CHARS:
            pos = at + 1
            continue
        # Verify there is a matching '('
        paren = text.find("(", at)
        if paren == -1:
            pos = at + 1
            continue
        # Extract preceding plain text
        if at > pos:
            segments.append(Segment(text[pos:at]))
        # Parse the tag
        attrs, content_end = _parse_tag(text, at)
        content_start = at + 1 + len(attrs) + 1
        content = text[content_start:content_end]
        fg, bg, flags = _parse_attrs(attrs)
        inner = parse_markup(content)
        for seg in inner:
            if fg is not None and seg.fg is None:
                seg.fg = fg
            if bg is not None and seg.bg is None:
                seg.bg = bg
            seg.style_flags |= flags
        segments.extend(inner)
        pos = content_end + 1
    if pos < len(text):
        segments.append(Segment(text[pos:]))
    return segments
