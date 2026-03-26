# -*- coding: utf-8 -*-
"""
Module: pigit/termui/text.py
Description: Display width and ANSI stripping — single implementation (no legacy import).
Author: Project Team
Date: 2026-03-26
"""

from __future__ import annotations

import re
from typing import Pattern

from pigit.termui.wcwidth_table import get_width

__all__ = ["get_width", "plain"]

_STYLE_ANSI_RE: Pattern[str] = re.compile(r"\033\[\d+;\d?;?\d*;?\d*;?\d*m|\033\[\d+m")


def plain(text: str) -> str:
    """Remove color ANSI sequences from text."""

    return _STYLE_ANSI_RE.sub("", text)
