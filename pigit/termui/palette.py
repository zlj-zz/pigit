"""
Module: pigit/termui/palette.py
Description: Default terminal color palette constants.
Author: Zev
Date: 2026-04-27
"""

from __future__ import annotations

# ── Pure color names ──

BLACK: tuple[int, int, int] = (0, 0, 0)
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

# Extended palette
SKY_BLUE: tuple[int, int, int] = (135, 206, 250)
TOMATO: tuple[int, int, int] = (255, 99, 71)
KHAKI: tuple[int, int, int] = (240, 230, 140)
PINK: tuple[int, int, int] = (255, 192, 203)
VIOLET_RED: tuple[int, int, int] = (199, 21, 133)
PALE_GREEN: tuple[int, int, int] = (152, 251, 152)

# Dark theme specific
CHARCOAL: tuple[int, int, int] = (24, 24, 24)
GRAPHITE: tuple[int, int, int] = (30, 30, 30)
GUNMETAL: tuple[int, int, int] = (42, 45, 46)
STEEL: tuple[int, int, int] = (55, 55, 61)
NAVY_GRAY: tuple[int, int, int] = (40, 45, 55)
SLATE_DARK: tuple[int, int, int] = (45, 45, 50)

# Semantic dark colors
FOREST: tuple[int, int, int] = (35, 65, 45)
OLIVE: tuple[int, int, int] = (75, 65, 20)
MAROON: tuple[int, int, int] = (80, 40, 40)
DARK_CRIMSON: tuple[int, int, int] = (55, 35, 35)
MIDNIGHT: tuple[int, int, int] = (30, 50, 75)

# Light / bright
ALMOST_WHITE: tuple[int, int, int] = (220, 220, 220)
MAGENTA: tuple[int, int, int] = (240, 130, 200)
AMBER: tuple[int, int, int] = (255, 175, 80)

# ── Legacy role assignments (kept for backward compat) ──
DEFAULT_FG = PEARL
DEFAULT_FG_DIM = SLATE
DEFAULT_BG = INK

BG_HOVER = GUNMETAL
BG_ACTIVE = NAVY_GRAY
BG_DANGER_ROW = DARK_CRIMSON

# ── Style flags (bitmask) ──
STYLE_BOLD = 1 << 0
STYLE_DIM = 1 << 1
STYLE_ITALIC = 1 << 2
STYLE_UNDERLINE = 1 << 3
STYLE_REVERSE = 1 << 4
