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

    # ── General state semantics (usage-named, replacing accent_* colors) ──
    fg_success: tuple[int, int, int] = palette.GREEN
    fg_warning: tuple[int, int, int] = palette.YELLOW
    fg_danger: tuple[int, int, int] = palette.RED
    fg_info: tuple[int, int, int] = palette.BLUE

    # ── Git object types ──
    fg_local_branch: tuple[int, int, int] = palette.GREEN
    fg_remote_branch: tuple[int, int, int] = palette.MAGENTA
    fg_tag: tuple[int, int, int] = palette.SKY_BLUE
    fg_tag_parent: tuple[int, int, int] = palette.AMBER
    fg_head_commit: tuple[int, int, int] = palette.BLUE
    fg_unpushed_commit: tuple[int, int, int] = palette.YELLOW

    # ── Panel / title / search ──
    fg_branch_name: tuple[int, int, int] = palette.PEARL
    fg_panel_title: tuple[int, int, int] = palette.PEARL
    fg_search_match: tuple[int, int, int] = palette.PEARL
    fg_file_history_link: tuple[int, int, int] = palette.SKY_BLUE

    # ── Diff viewer ──
    bg_diff_add: tuple[int, int, int] = palette.FOREST
    bg_diff_del: tuple[int, int, int] = palette.MAROON
    bg_diff_hunk: tuple[int, int, int] = palette.GRAPHITE
    bg_diff_context: tuple[int, int, int] = palette.DEFAULT_BG
    fg_diff_add: tuple[int, int, int] = palette.GREEN
    fg_diff_del: tuple[int, int, int] = palette.RED

    # ── Overlay ──
    bg_overlay: tuple[int, int, int] = palette.SLATE_DARK
    bg_overlay_dim: tuple[int, int, int] = palette.NAVY_GRAY

    # ── Chrome (status bar) ──
    bg_chrome: tuple[int, int, int] = palette.INK
    fg_chrome_active: tuple[int, int, int] = palette.ALMOST_WHITE
    fg_chrome_inactive: tuple[int, int, int] = palette.SLATE

    # ── Borders ──
    border: tuple[int, int, int] = palette.GUNMETAL
    divider: tuple[int, int, int] = palette.GUNMETAL
    separator: tuple[int, int, int] = palette.GUNMETAL

    # ── Staged files (commit editor) ──
    fg_staged_added: tuple[int, int, int] = palette.GREEN
    fg_staged_modified: tuple[int, int, int] = palette.YELLOW
    fg_staged_deleted: tuple[int, int, int] = palette.RED
    fg_staged_renamed: tuple[int, int, int] = palette.PURPLE
    fg_staged_copied: tuple[int, int, int] = palette.YELLOW

    # ── Syntax highlighting ──
    fg_syntax_keyword: tuple[int, int, int] = palette.PURPLE
    fg_syntax_string: tuple[int, int, int] = palette.GREEN
    fg_syntax_comment: tuple[int, int, int] = palette.SLATE
    fg_syntax_function: tuple[int, int, int] = palette.BLUE
    fg_syntax_number: tuple[int, int, int] = palette.MAGENTA
    fg_syntax_type: tuple[int, int, int] = palette.CYAN

    # ── File history header ──
    bg_file_history_header: tuple[int, int, int] = palette.GREEN
    fg_file_history_header: tuple[int, int, int] = palette.BLACK


# Global singleton theme instance.
THEME = FlatTheme()
