# -*- coding: utf-8 -*-
"""
Module: pigit/app_theme.py
Description: Flat color theme for Pigit Neo UI.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FlatTheme:
    """TrueColor palette for the Pigit Neo flat design system.

    Inspired by VS Code Dark Modern: neutral dark greys, crisp foregrounds,
    and IDE-standard accent colors.
    """

    # Background layers (deepest to most elevated)
    bg_base: tuple[int, int, int] = (24, 24, 24)
    bg_panel: tuple[int, int, int] = (30, 30, 30)
    bg_hover: tuple[int, int, int] = (42, 45, 46)
    bg_active: tuple[int, int, int] = (55, 55, 61)

    # State backgrounds (full-row semantic colors)
    bg_success: tuple[int, int, int] = (35, 65, 45)
    bg_warning: tuple[int, int, int] = (75, 65, 20)
    bg_danger: tuple[int, int, int] = (80, 40, 40)
    bg_info: tuple[int, int, int] = (30, 50, 75)

    # Foreground colors
    fg_primary: tuple[int, int, int] = (220, 220, 220)
    fg_muted: tuple[int, int, int] = (150, 150, 150)
    fg_dim: tuple[int, int, int] = (100, 100, 100)

    # Accent colors — VS Code IDE standard palette
    accent_cyan: tuple[int, int, int] = (78, 201, 176)
    accent_green: tuple[int, int, int] = (137, 209, 133)
    accent_yellow: tuple[int, int, int] = (220, 205, 100)
    accent_red: tuple[int, int, int] = (244, 135, 113)
    accent_blue: tuple[int, int, int] = (150, 200, 255)
    accent_purple: tuple[int, int, int] = (210, 170, 240)

    # Diff viewer backgrounds
    bg_diff_add: tuple[int, int, int] = (35, 65, 45)
    bg_diff_del: tuple[int, int, int] = (80, 40, 40)
    bg_diff_hunk: tuple[int, int, int] = (30, 30, 30)


# Global singleton theme instance.
THEME = FlatTheme()
