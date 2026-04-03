# -*- coding: utf-8 -*-
"""
Module: pigit/termui/text.py
Description: Display width and ANSI stripping — single implementation (no legacy import).
Author: Project Team
Date: 2026-03-26
"""

from __future__ import annotations

import re
from typing import List, Pattern

from pigit.termui.wcwidth_table import get_width

__all__ = ["get_width", "plain", "sanitize_for_display"]

_STYLE_ANSI_RE: Pattern[str] = re.compile(r"\033\[\d+;\d?;?\d*;?\d*;?\d*m|\033\[\d+m")


def plain(text: str) -> str:
    """Remove color ANSI sequences from text."""

    return _STYLE_ANSI_RE.sub("", text)


def sanitize_for_display(text: str, max_scalars: int = 4096) -> str:
    """
    Strip ANSI SGR and unsafe control characters for overlay text (no raw ESC).

    Truncates to ``max_scalars`` Unicode scalar values. Newlines are preserved.
    """

    stripped = plain(text.replace("\x1b", ""))
    out: List[str] = []
    n = 0
    for ch in stripped:
        o = ord(ch)
        if o == 0x7F or (o < 32 and ch not in "\n\r\t"):
            continue
        out.append(ch)
        n += 1
        if n >= max_scalars:
            break
    return "".join(out)
