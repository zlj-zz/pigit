"""
Module: pigit/app_theme.py
Description: Flat color theme for Pigit Neo UI.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from dataclasses import dataclass

from pigit.termui import palette


@dataclass(frozen=True)
class FlatTheme:
    """TrueColor palette for the Pigit Neo flat design system.

    Inspired by VS Code Dark Modern: neutral dark greys, crisp foregrounds,
    and IDE-standard accent colors.
    """

    # Background layers (deepest to most elevated)
    bg_base: tuple[int, int, int] = palette.CHARCOAL
    bg_panel: tuple[int, int, int] = palette.GRAPHITE
    bg_hover: tuple[int, int, int] = palette.GUNMETAL
    bg_active: tuple[int, int, int] = palette.STEEL

    # State backgrounds (full-row semantic colors)
    bg_success: tuple[int, int, int] = palette.FOREST
    bg_warning: tuple[int, int, int] = palette.OLIVE
    bg_danger: tuple[int, int, int] = palette.MAROON
    bg_info: tuple[int, int, int] = palette.MIDNIGHT

    # Foreground colors
    fg_primary: tuple[int, int, int] = palette.ALMOST_WHITE
    fg_muted: tuple[int, int, int] = palette.MUTED
    fg_dim: tuple[int, int, int] = palette.DIM

    # Accent colors — VS Code IDE standard palette
    accent_cyan: tuple[int, int, int] = palette.CYAN
    accent_green: tuple[int, int, int] = palette.GREEN
    accent_yellow: tuple[int, int, int] = palette.YELLOW
    accent_red: tuple[int, int, int] = palette.RED
    accent_blue: tuple[int, int, int] = palette.BLUE
    accent_purple: tuple[int, int, int] = palette.PURPLE
    accent_magenta: tuple[int, int, int] = palette.MAGENTA
    accent_orange: tuple[int, int, int] = palette.AMBER
    accent_pearl: tuple[int, int, int] = palette.PEARL
    accent_sky_blue: tuple[int, int, int] = palette.SKY_BLUE

    # Diff viewer backgrounds
    bg_diff_add: tuple[int, int, int] = palette.FOREST
    bg_diff_del: tuple[int, int, int] = palette.MAROON
    bg_diff_hunk: tuple[int, int, int] = palette.GRAPHITE

    # Overlay backgrounds
    bg_palette: tuple[int, int, int] = palette.SLATE_DARK

    # File history header
    bg_file_history_header: tuple[int, int, int] = palette.GREEN
    fg_file_history_header: tuple[int, int, int] = palette.BLACK


# Global singleton theme instance.
THEME = FlatTheme()
