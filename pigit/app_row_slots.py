"""
Module: pigit/app_row_slots.py
Description: Fixed-width prefix lanes shared by the list panels' rows.
Author: Zev
Date: 2026-10-07
"""

from __future__ import annotations

from collections.abc import Sequence

from pigit.termui import Segment
from pigit.termui.wcwidth_table import wcswidth

#: Widths of the prefix lanes a panel returns as the ``left`` of a row.
#:
#: Lanes are ordered and each panel fills a leading run of them: Status uses
#: the status lane and the icon lane, Branch and Stash only the status lane.
#: A panel may stop early, but it must fill the lanes it does use to their
#: full width -- padding with spaces rather than letting an empty lane
#: collapse. A lane whose width changes from row to row moves the identity
#: column with it, which is what put Status's directory rows three columns
#: off its file rows.
SLOT_STATUS_W = 2
SLOT_ICON_W = 2


def status_lane(
    content: Sequence[Segment], *, pad_fg: tuple[int, int, int]
) -> list[Segment]:
    """Fill the status lane (:data:`SLOT_STATUS_W` cells) with *content*.

    Args:
        content: The lane's own segments, already styled.
        pad_fg: Foreground for the padding when *content* is narrower.

    Returns:
        *content*, padded with spaces to the lane width.
    """
    return pad_to_width(content, SLOT_STATUS_W, pad_fg=pad_fg)


def icon_lane(
    content: Sequence[Segment], *, pad_fg: tuple[int, int, int]
) -> list[Segment]:
    """Fill the icon lane (:data:`SLOT_ICON_W` cells) with *content*.

    Args:
        content: The lane's own segments, already styled.
        pad_fg: Foreground for the padding when *content* is narrower.

    Returns:
        *content*, padded with spaces to the lane width.
    """
    return pad_to_width(content, SLOT_ICON_W, pad_fg=pad_fg)


def pad_to_width(
    segments: Sequence[Segment],
    width: int,
    *,
    pad_fg: tuple[int, int, int],
    at_front: bool = False,
) -> list[Segment]:
    """Pad *segments* with ``pad_fg`` spaces to *width* cells.

    Padding a *lane* at the back keeps the identity column still. Padding a
    *right-anchored block* at the front does the same for it: the framework
    anchors the block at ``w - block_width``, so a block narrower than its
    neighbours starts further right and every column inside it floats from row
    to row. Giving every row's block the panel's widest width pins their common
    left edge.

    Args:
        segments: The content to pad, already styled.
        width: Target width in display cells.
        pad_fg: Foreground for the padding.
        at_front: Pad before *segments* instead of after.

    Returns:
        The padded segments. Content already at or past *width* is returned
        untouched -- a width is a minimum to fill, not a budget to spend, so
        overfilling it is a layout bug rather than something to truncate here.
    """
    fill = width - sum(wcswidth(seg.text) for seg in segments)
    if fill <= 0:
        return list(segments)
    filler = Segment(" " * fill, fg=pad_fg)
    return [filler, *segments] if at_front else [*segments, filler]
