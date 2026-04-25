# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_color.py
Description: TrueColor rendering support with automatic terminal capability fallback.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from functools import lru_cache
from typing import Optional

_logger = logging.getLogger(__name__)


class ColorMode(Enum):
    """Terminal color output capability levels."""

    TRUECOLOR = "truecolor"
    COLOR_256 = "256"
    COLOR_16 = "16"
    NONE = "none"


# Standard 16-color ANSI palette (RGB values)
_ANSI_16_PALETTE: list[tuple[int, int, int]] = [
    (0, 0, 0),  # 0  black
    (128, 0, 0),  # 1  red
    (0, 128, 0),  # 2  green
    (128, 128, 0),  # 3  yellow
    (0, 0, 128),  # 4  blue
    (128, 0, 128),  # 5  magenta
    (0, 128, 128),  # 6  cyan
    (192, 192, 192),  # 7  white
    (128, 128, 128),  # 8  bright black
    (255, 0, 0),  # 9  bright red
    (0, 255, 0),  # 10 bright green
    (255, 255, 0),  # 11 bright yellow
    (0, 0, 255),  # 12 bright blue
    (255, 0, 255),  # 13 bright magenta
    (0, 255, 255),  # 14 bright cyan
    (255, 255, 255),  # 15 bright white
]


def _detect_color_mode() -> ColorMode:
    """Detect terminal color capability from environment variables."""
    force = os.environ.get("PIGIT_COLOR_MODE", "").lower()
    if force:
        try:
            return ColorMode(force)
        except ValueError:
            _logger.warning("Invalid PIGIT_COLOR_MODE=%r, using auto-detect", force)

    term = os.environ.get("TERM", "")
    colorterm = os.environ.get("COLORTERM", "")

    if colorterm in ("truecolor", "24bit"):
        return ColorMode.TRUECOLOR
    if "256color" in term:
        return ColorMode.COLOR_256
    if term in ("xterm", "screen", "vt100"):
        return ColorMode.COLOR_16
    return ColorMode.COLOR_256  # Default optimistic fallback


class ColorAdapter:
    """Converts RGB values to ANSI SGR sequences based on terminal capability.

    Quantization results are cached via :func:`functools.lru_cache` for
    performance.  The adapter is stateless and safe to share across threads.
    """

    def __init__(self, mode: Optional[ColorMode] = None) -> None:
        self.mode = mode or _detect_color_mode()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def fg_sequence(self, rgb: tuple[int, int, int]) -> str:
        """Return ANSI SGR sequence for foreground color."""
        code = self._quantized_code(rgb)
        if code is None:
            return ""
        if self.mode == ColorMode.TRUECOLOR:
            return f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"
        return f"\033[{code}m"

    def bg_sequence(self, rgb: tuple[int, int, int]) -> str:
        """Return ANSI SGR sequence for background color."""
        code = self._quantized_code(rgb)
        if code is None:
            return ""
        if self.mode == ColorMode.TRUECOLOR:
            return f"\033[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m"
        return f"\033[{code + 10}m"

    def bold_sequence(self, bold: bool) -> str:
        """Return ANSI SGR sequence for bold weight."""
        return "\033[1m" if bold else "\033[22m"

    def reset_sequence(self) -> str:
        """Return ANSI reset sequence."""
        return "\033[0m"

    # ------------------------------------------------------------------ #
    # Quantization
    # ------------------------------------------------------------------ #

    def _quantized_code(self, rgb: tuple[int, int, int]) -> Optional[int]:
        """Return ANSI color code for the given RGB, or None for NONE mode."""
        if self.mode == ColorMode.NONE:
            return None
        if self.mode == ColorMode.TRUECOLOR:
            return 0  # Unused for truecolor; caller builds 38;2;R;G;B
        if self.mode == ColorMode.COLOR_256:
            return _nearest_256(rgb)
        return _nearest_16(rgb)


# ------------------------------------------------------------------ #
# 256-color quantization (6x6x6 cube + grayscale)
# ------------------------------------------------------------------ #

@lru_cache(maxsize=512)
def _nearest_256(rgb: tuple[int, int, int]) -> int:
    """Map RGB to nearest xterm-256 color code (0-255).

    Codes 0-15 are the standard 16 colors, 16-231 are the 6x6x6 cube,
    and 232-255 are grayscale ramp.
    """
    r, g, b = rgb

    # Try exact match in 16-color palette first
    for i, pal in enumerate(_ANSI_16_PALETTE):
        if rgb == pal:
            return i

    # 6x6x6 color cube (codes 16-231)
    # Each dimension has 6 levels: 0, 95, 135, 175, 215, 255
    cube_levels = [0, 95, 135, 175, 215, 255]
    ri = _find_nearest_index(r, cube_levels)
    gi = _find_nearest_index(g, cube_levels)
    bi = _find_nearest_index(b, cube_levels)
    cube_color = (ri * 36) + (gi * 6) + bi + 16
    cube_rgb = (cube_levels[ri], cube_levels[gi], cube_levels[bi])
    cube_dist = _color_distance(rgb, cube_rgb)

    # Grayscale ramp (codes 232-255): 24 shades from 8 to 238
    gray = int(round((r + g + b) / 3.0))
    gray_idx = _find_nearest_index(gray, _GRAYSCALE_LEVELS)
    gray_color = 232 + gray_idx
    gray_rgb = (_GRAYSCALE_LEVELS[gray_idx],) * 3
    gray_dist = _color_distance(rgb, gray_rgb)

    return cube_color if cube_dist <= gray_dist else gray_color


_GRAYSCALE_LEVELS: list[int] = [
    8,
    18,
    28,
    38,
    48,
    58,
    68,
    78,
    88,
    98,
    108,
    118,
    128,
    138,
    148,
    158,
    168,
    178,
    188,
    198,
    208,
    218,
    228,
    238,
]


# ------------------------------------------------------------------ #
# 16-color quantization
# ------------------------------------------------------------------ #

@lru_cache(maxsize=256)
def _nearest_16(rgb: tuple[int, int, int]) -> int:
    """Map RGB to nearest standard 16-color ANSI code (0-15)."""
    best_idx = 0
    best_dist = float("inf")
    for i, pal in enumerate(_ANSI_16_PALETTE):
        dist = _color_distance(rgb, pal)
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    return best_idx


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    """Squared Euclidean distance between two RGB triples."""
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def _find_nearest_index(value: int, levels: list[int]) -> int:
    """Return index of nearest level to value."""
    best = 0
    best_dist = abs(value - levels[0])
    for i, lvl in enumerate(levels[1:], 1):
        dist = abs(value - lvl)
        if dist < best_dist:
            best_dist = dist
            best = i
    return best
