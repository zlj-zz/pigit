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

# Fraction of the blend toward the brand accent for the hunk header tone:
# 0.30 reads as a clearly distinct block while keeping ~6:1 contrast.
_HUNK_TONE_BLEND = 0.30

# Commit panel: cursor-selected row background.
_HEAD_ROW_BLEND = 0.15
_HEAD_ROW_INACTIVE_BLEND = 0.10

# Heatmap current-week side bars: muted accent, not full fg_accent brightness.
_CONTRIB_WEEK_FRAME_BLEND = 0.35

# Author line chart: six equal-blend hues (between muted chrome and full palette).
_CHART_AUTHOR_BLEND = 0.55
_CHART_AUTHOR_HUES: tuple[tuple[int, int, int], ...] = (
    palette.ACCENT,
    palette.GREEN,
    palette.AMBER,
    palette.MAGENTA,
    palette.CYAN,
    palette.PURPLE,
)


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

    # Cursor-selected commit row background.
    bg_commit_selected: tuple[int, int, int] = palette.blend(
        palette.STEEL, palette.ACCENT, _HEAD_ROW_BLEND
    )
    bg_commit_selected_inactive: tuple[int, int, int] = palette.blend(
        palette.CHARCOAL, palette.ACCENT, _HEAD_ROW_INACTIVE_BLEND
    )

    # Panel / title / search
    fg_branch_name: tuple[int, int, int] = palette.PEARL
    fg_panel_title: tuple[int, int, int] = palette.PEARL
    fg_search_match: tuple[int, int, int] = palette.PEARL
    fg_file_history_link: tuple[int, int, int] = palette.SKY_BLUE

    # Diff viewer (extra slots beyond Theme diff add/del)
    # Hunk header tone derives from the brand accent so it follows accent
    # changes without hand-tuning. blend(CHARCOAL, ACCENT, 0.30) reads as a
    # clearly distinct block (0.18 was barely distinguishable from the panel)
    # while keeping ~6:1 contrast against fg_diff_hunk.
    bg_diff_hunk: tuple[int, int, int] = palette.blend(
        palette.CHARCOAL, palette.ACCENT, _HUNK_TONE_BLEND
    )
    fg_diff_hunk: tuple[int, int, int] = palette.PEARL
    bg_diff_context: tuple[int, int, int] = palette.INK
    bg_word_diff_add: tuple[int, int, int] = (58, 118, 68)
    bg_word_diff_del: tuple[int, int, int] = (148, 58, 55)

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

    # Contribution report: six soft, equal-blend author line colors (hash-assigned).
    chart_author_colors: tuple[tuple[int, int, int], ...] = tuple(
        palette.blend(palette.STEEL, hue, _CHART_AUTHOR_BLEND)
        for hue in _CHART_AUTHOR_HUES
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

    # Contribution heatmap: vertical side bars for the current week column.
    fg_contrib_week_frame: tuple[int, int, int] = palette.blend(
        palette.SLATE, palette.ACCENT, _CONTRIB_WEEK_FRAME_BLEND
    )


# Global singleton theme instance.
THEME = PigitTheme()
