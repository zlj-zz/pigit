"""
Module: pigit/termui/viewport_hit.py
Description: Viewport hit contract for scrollable row-table widgets.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

# Maximum gap between two left presses that still counts as one double-click.
# Single source of truth for every widget that detects double-clicks.
DOUBLE_CLICK_MS = 400


@dataclass(frozen=True)
class LayoutRow:
    """One render line of a viewport row table.

    ``selectable_index`` mirrors the ``selectable_i`` produced by
    ``help_format`` — ``None`` for group headers, blank separators and wrapped
    continuation lines. Visibility is expressed by ``hit_row``'s viewport
    range check, not by a stored row number.
    """

    selectable_index: int | None


@dataclass(frozen=True)
class ViewportLayout:
    """Geometry of one paint cycle for a top-down scrollable row table.

    Built once during ``_rebuild``; mouse handling reads it without re-wrapping
    text or re-measuring segments. Hit invariant: a component-local 1-based
    ``event.row`` maps to the render table via
    ``render_index = scroll_offset + (event.row - content_origin_row) - 1``.
    The subtraction of a 0-based ``content_origin`` row from a 1-based event
    row yields the content-local 1-based row for any border thickness.

    Attributes:
        content_origin: 0-based ``(row, col)`` of the content area on the
            component surface (as returned by ``BoxFrame.content_rect``).
        content_width: Content area width in cells.
        viewport_height: Number of visible rows.
        scroll_offset: Index of the first row shown at the viewport top.
        rows: Full render-line table (not just the visible slice).
    """

    content_origin: tuple[int, int]
    content_width: int
    viewport_height: int
    scroll_offset: int
    rows: tuple[LayoutRow, ...]


def build_viewport_layout(
    selectables: Sequence[int | None],
    *,
    content_origin: tuple[int, int],
    content_width: int,
    viewport_height: int,
    scroll_offset: int,
) -> ViewportLayout:
    """Derive viewport geometry from the paint line table.

    ``selectables`` holds the ``selectable_index`` of every render line (the
    second element of each ``build_binding_browser_lines`` tuple). Pure
    geometry: layout and painted rows share one wrap source, so clicks can
    never drift from what is rendered. ``viewport_height`` and
    ``scroll_offset`` drive ``hit_row``'s visibility check; rows here are the
    full table, not the visible slice.
    """
    rows = [LayoutRow(sel) for sel in selectables]
    return ViewportLayout(
        content_origin=content_origin,
        content_width=content_width,
        viewport_height=viewport_height,
        scroll_offset=scroll_offset,
        rows=tuple(rows),
    )


def hit_row(local_row: int, local_col: int, layout: ViewportLayout) -> int | None:
    """Return the selectable index under a content-local click, else ``None``.

    Args:
        local_row: 1-based content-local row (``event.row - content_origin[0]``).
        local_col: 1-based content-local column (``event.col - content_origin[1]``).
        layout: Layout built during the last ``_rebuild``.

    Returns:
        The clicked line's ``selectable_index`` — ``None`` for group headers,
        blank separators, wrapped continuations, clicks outside the content
        column band, and rows scrolled out of view.
    """
    if local_col < 1 or local_col > layout.content_width:
        return None
    if local_row < 1 or local_row > layout.viewport_height:
        return None
    render_index = layout.scroll_offset + local_row - 1
    if render_index < 0 or render_index >= len(layout.rows):
        return None
    return layout.rows[render_index].selectable_index
