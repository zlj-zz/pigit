"""
Module: pigit/termui/feedback.py
Description: Feedback semantic levels (kind) and their visual style mapping.
Author: Zev
Date: 2026-08-14
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from . import palette


class FeedbackKind(str, Enum):
    """Semantic level of a transient feedback message.

    ``None`` is the neutral level: no glyph, no semantic color (default for
    plain toasts). Spinners apply INFO chrome without the kind glyph.
    """

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class FeedbackStyle:
    """Visual style for one feedback kind: foreground, glyph, and text style."""

    fg: tuple[int, int, int]
    glyph: str
    style_flags: int = 0


# Kind -> style. Glyphs are width-1, text-presentation (no emoji risk).
# Colors reuse palette semantic hues (== app_theme.fg_*), no new colors.
KIND_STYLE: dict[FeedbackKind, FeedbackStyle] = {
    FeedbackKind.INFO: FeedbackStyle(palette.BLUE, "i"),
    FeedbackKind.SUCCESS: FeedbackStyle(palette.GREEN, "✓"),
    FeedbackKind.WARNING: FeedbackStyle(palette.YELLOW, "!"),
    FeedbackKind.ERROR: FeedbackStyle(palette.RED, "✗", palette.STYLE_BOLD),
}


def style_for(kind: FeedbackKind | None) -> FeedbackStyle | None:
    """Return the style for a kind, or ``None`` for the neutral level."""
    if kind is None:
        return None
    return KIND_STYLE.get(kind)
