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

from . import palette

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

_XTERM_CUBE_LEVELS = (0, 95, 135, 175, 215, 255)
_ANSI_16_INDEX = {rgb: index for index, rgb in enumerate(_ANSI_16_PALETTE)}


def _fg_sgr_16(index: int) -> str:
    """Foreground SGR for ANSI-16 index 0-15."""
    return f"\033[{30 + index}m" if index < 8 else f"\033[{82 + index}m"


def _bg_sgr_16(index: int) -> str:
    """Background SGR for ANSI-16 index 0-15."""
    return f"\033[{40 + index}m" if index < 8 else f"\033[{92 + index}m"


def xterm256_to_rgb(index: int) -> tuple[int, int, int]:
    """Convert an xterm-256 color index (0-255) to RGB."""
    n = max(0, min(255, int(index)))
    if n < 16:
        return _ANSI_16_PALETTE[n]
    if n < 232:
        n -= 16
        red, green, blue = n // 36, (n // 6) % 6, n % 6
        return (
            _XTERM_CUBE_LEVELS[red],
            _XTERM_CUBE_LEVELS[green],
            _XTERM_CUBE_LEVELS[blue],
        )
    gray = 8 + (n - 232) * 10
    return (gray, gray, gray)


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

    def __init__(self, mode: ColorMode | None = None) -> None:
        self.mode = mode or _detect_color_mode()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def fg_sequence(self, rgb: tuple[int, int, int]) -> str:
        """Return ANSI SGR sequence for foreground color.

        RGB values that are exact ANSI-16 slots are emitted as indexed
        SGR (``31m`` / ``91m``) so the terminal theme applies. Other RGB
        values use truecolor or quantized fallbacks.
        """
        if self.mode == ColorMode.NONE:
            return ""
        indexed = _ANSI_16_INDEX.get(rgb)
        if indexed is not None:
            return _fg_sgr_16(indexed)
        if self.mode == ColorMode.TRUECOLOR:
            return f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"
        if self.mode == ColorMode.COLOR_256:
            return f"\033[38;5;{_nearest_256(rgb)}m"
        return _fg_sgr_16(_nearest_16(rgb))

    def bg_sequence(self, rgb: tuple[int, int, int]) -> str:
        """Return ANSI SGR sequence for background color."""
        if self.mode == ColorMode.NONE:
            return ""
        indexed = _ANSI_16_INDEX.get(rgb)
        if indexed is not None:
            return _bg_sgr_16(indexed)
        if self.mode == ColorMode.TRUECOLOR:
            return f"\033[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m"
        if self.mode == ColorMode.COLOR_256:
            return f"\033[48;5;{_nearest_256(rgb)}m"
        return _bg_sgr_16(_nearest_16(rgb))

    def style_sequence(self, flags: int) -> str:
        """Return combined ANSI SGR sequence for style flags."""
        if not flags:
            return ""
        parts = []
        if flags & palette.STYLE_BOLD:
            parts.append("1")
        if flags & palette.STYLE_DIM:
            parts.append("2")
        if flags & palette.STYLE_ITALIC:
            parts.append("3")
        if flags & palette.STYLE_UNDERLINE:
            parts.append("4")
        if flags & palette.STYLE_REVERSE:
            parts.append("7")
        return f"\033[{';'.join(parts)}m"

    def reset_style_sequence(self) -> str:
        """Reset all style attributes (not colors).

        SGR codes:
        - 22 = normal intensity (off bold / off dim)
        - 23 = off italic
        - 24 = off underline
        - 27 = off reverse
        """
        return "\033[22;23;24;27m"

    def reset_sequence(self) -> str:
        """Return ANSI reset sequence."""
        return "\033[0m"


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
    cube_levels = _XTERM_CUBE_LEVELS
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
    gray_val = _GRAYSCALE_LEVELS[gray_idx]
    gray_rgb = (gray_val, gray_val, gray_val)
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


def _find_nearest_index(value: int, levels: tuple[int, ...] | list[int]) -> int:
    """Return index of nearest level to value."""
    best = 0
    best_dist = abs(value - levels[0])
    for i, lvl in enumerate(levels[1:], 1):
        dist = abs(value - lvl)
        if dist < best_dist:
            best_dist = dist
            best = i
    return best
