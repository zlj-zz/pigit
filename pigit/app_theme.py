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

    ``fg_primary`` / ``fg_dim`` override the framework defaults (PEARL / SLATE)
    for product chrome contrast. Graph and contribution colors live here so
    panels never hardcode ``palette.*`` RGB values.
    """

    # Product text hierarchy (overrides Theme.ALMOST_WHITE / DIM).
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

    # Chrome / header
    fg_header_repo: tuple[int, int, int] = palette.AMBER

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

    # Inline commit merge-graph lane colors (cycled by lane index).
    graph_lane_colors: tuple[tuple[int, int, int], ...] = (
        palette.SKY_BLUE,
        palette.GREEN,
        palette.PURPLE,
        palette.BLUE,
        palette.RED,
    )

    # Contribution report: author line-chart series colors.
    chart_author_colors: tuple[tuple[int, int, int], ...] = (
        palette.SKY_BLUE,
        palette.YELLOW,
        palette.PURPLE,
        palette.RED,
        palette.GREEN,
        palette.BLUE,
    )

    # Contribution heatmap intensity 0..5 (level 0 stays slightly lighter
    # so empty cells read on the panel background).
    contrib_heatmap_colors: tuple[tuple[int, int, int], ...] = (
        (100, 100, 110),
        (155, 233, 168),
        (105, 210, 130),
        (64, 196, 99),
        (48, 161, 78),
        (33, 110, 57),
    )


# Global singleton theme instance.
THEME = PigitTheme()
