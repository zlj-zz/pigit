"""
Module: pigit/app_theme.py
Description: Pigit application theme extending termui semantic Theme with Git-specific colors.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from dataclasses import dataclass

from pigit.termui import palette
from pigit.termui.theme import Theme


@dataclass(frozen=True)
class PigitTheme(Theme):
    """Pigit Neo flat design system with Git and chrome-specific color slots.

    Extends :class:`Theme` with application-only semantic colors. Base widget
    roles and syntax tokens live on :class:`Theme`.
    """

    # Base widget roles (match legacy palette.DEFAULT_FG / DEFAULT_FG_DIM)
    fg_primary: tuple[int, int, int] = palette.PEARL
    fg_dim: tuple[int, int, int] = palette.SLATE

    # State backgrounds (full-row semantic colors)
    bg_success: tuple[int, int, int] = palette.FOREST
    bg_warning: tuple[int, int, int] = palette.OLIVE
    bg_danger: tuple[int, int, int] = palette.MAROON
    bg_info: tuple[int, int, int] = palette.MIDNIGHT

    # Git object types
    fg_local_branch: tuple[int, int, int] = palette.GREEN
    fg_remote_branch: tuple[int, int, int] = palette.MAGENTA
    fg_tag: tuple[int, int, int] = palette.SKY_BLUE
    fg_tag_parent: tuple[int, int, int] = palette.AMBER
    fg_head_commit: tuple[int, int, int] = palette.BLUE
    fg_unpushed_commit: tuple[int, int, int] = palette.YELLOW

    # Panel / title / search
    fg_branch_name: tuple[int, int, int] = palette.PEARL
    fg_panel_title: tuple[int, int, int] = palette.PEARL
    fg_search_match: tuple[int, int, int] = palette.PEARL
    fg_file_history_link: tuple[int, int, int] = palette.SKY_BLUE

    # Diff viewer (extra slots beyond Theme diff add/del)
    bg_diff_hunk: tuple[int, int, int] = palette.GRAPHITE
    bg_diff_context: tuple[int, int, int] = palette.INK
    bg_word_diff_add: tuple[int, int, int] = (50, 105, 60)
    bg_word_diff_del: tuple[int, int, int] = (120, 50, 50)

    # Overlay
    bg_overlay_dim: tuple[int, int, int] = palette.NAVY_GRAY

    # Chrome (status bar)
    fg_chrome_active: tuple[int, int, int] = palette.ALMOST_WHITE
    fg_chrome_inactive: tuple[int, int, int] = palette.SLATE
    fg_header_repo: tuple[int, int, int] = palette.AMBER
    fg_header_branch: tuple[int, int, int] = palette.CYAN

    # Borders
    divider: tuple[int, int, int] = palette.GUNMETAL
    separator: tuple[int, int, int] = palette.GUNMETAL

    # Staged files (commit editor)
    fg_staged_added: tuple[int, int, int] = palette.GREEN
    fg_staged_modified: tuple[int, int, int] = palette.YELLOW
    fg_staged_deleted: tuple[int, int, int] = palette.RED
    fg_staged_renamed: tuple[int, int, int] = palette.PURPLE
    fg_staged_copied: tuple[int, int, int] = palette.YELLOW

    # File history header
    bg_file_history_header: tuple[int, int, int] = palette.GREEN
    fg_file_history_header: tuple[int, int, int] = palette.BLACK


# Global singleton theme instance.
THEME = PigitTheme()
