# -*- coding: utf-8 -*-
"""
Module: pigit/termui/palette.py
Description: Default terminal color palette constants.
Author: Zev
Date: 2026-04-27
"""

from __future__ import annotations


PEARL: tuple[int, int, int] = (220, 220, 230)
SLATE: tuple[int, int, int] = (120, 120, 130)
INK: tuple[int, int, int] = (18, 18, 22)
PURPLE: tuple[int, int, int] = (210, 170, 240)
BLUE: tuple[int, int, int] = (150, 200, 255)
YELLOW: tuple[int, int, int] = (220, 205, 100)
CYAN: tuple[int, int, int] = (78, 201, 176)
GREEN: tuple[int, int, int] = (137, 209, 133)
RED: tuple[int, int, int] = (244, 135, 113)
MUTED: tuple[int, int, int] = (150, 150, 150)
DIM: tuple[int, int, int] = (100, 100, 100)

# ── Role assignments ──
DEFAULT_FG = PEARL
DEFAULT_FG_DIM = SLATE
DEFAULT_BG = INK

# ── Style flags (bitmask) ──
STYLE_BOLD = 1 << 0
STYLE_DIM = 1 << 1
STYLE_ITALIC = 1 << 2
STYLE_UNDERLINE = 1 << 3
STYLE_REVERSE = 1 << 4
