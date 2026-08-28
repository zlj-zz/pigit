"""
Module: pigit/termui/widgets/help_format.py
Description: Shared Help / Welcome binding group layout as segment rows.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Sequence

from .. import palette
from ..bindings import ExecutableBinding
from ..segment import Segment
from ..viewport_hit import ViewportLayout, build_viewport_layout
from ..wcwidth_table import wcswidth
from .help_panel import wrap_text

_GROUP_INDENT = 2
_KEY_DESC_GAP = 2
_CURSOR_COL_W = 2
_CURSOR_GLYPH = "›"


def build_binding_browser_lines(
    groups: Sequence[tuple[str, Sequence[ExecutableBinding]]],
    *,
    inner_width: int,
    key_fg: tuple[int, int, int] | None = None,
    desc_fg: tuple[int, int, int] | None = None,
    show_cursor: bool = False,
) -> list[tuple[list[Segment], int | None]]:
    """Lay out binding groups like the Help browser (optional cursor column).

    Args:
        groups: ``(title, executable rows)`` pairs.
        inner_width: Content width for description wrapping.
        key_fg: Key column color; ``None`` uses default foreground.
        desc_fg: Description color; ``None`` uses default foreground.
        show_cursor: When True, reserve a ``›`` column and mark first lines selectable.

    Returns:
        ``(segments, selectable_index)`` per rendered row; ``None`` when not selectable.
    """
    if not groups:
        return []
    cursor_w = _CURSOR_COL_W if show_cursor else 0
    max_key_w = 0
    for _title, entries in groups:
        for row in entries:
            max_key_w = max(max_key_w, wcswidth(row.keys_display))

    desc_avail = max(
        1,
        inner_width - _GROUP_INDENT - cursor_w - max_key_w - _KEY_DESC_GAP,
    )

    render: list[tuple[list[Segment], int | None]] = []
    selectable_i = 0
    for title, entries in groups:
        if not entries:
            continue
        header = f"[{title}]"
        render.append(([Segment(header, style_flags=palette.STYLE_BOLD)], None))
        for row in entries:
            wrapped = wrap_text(row.desc, desc_avail)
            for line_i, desc_line in enumerate(wrapped):
                if line_i == 0:
                    pad = max_key_w - wcswidth(row.keys_display)
                    seg: list[Segment] = [Segment(" " * _GROUP_INDENT)]
                    if show_cursor:
                        seg.append(Segment(" " * _CURSOR_COL_W))
                    if pad:
                        seg.append(Segment(" " * pad))
                    if key_fg is not None:
                        seg.append(
                            Segment(
                                row.keys_display,
                                fg=key_fg,
                                style_flags=palette.STYLE_BOLD,
                            )
                        )
                        seg.append(Segment(" " * _KEY_DESC_GAP))
                    else:
                        seg.append(Segment(row.keys_display + " " * _KEY_DESC_GAP))
                    seg.append(Segment(desc_line, fg=desc_fg))
                    render.append((seg, selectable_i if show_cursor else None))
                else:
                    indent = _GROUP_INDENT + cursor_w + max_key_w + _KEY_DESC_GAP
                    render.append(
                        (
                            [
                                Segment(" " * indent),
                                Segment(desc_line, fg=desc_fg),
                            ],
                            None,
                        )
                    )
            selectable_i += 1
        render.append(([], None))
    return render


def build_binding_browser_layout(
    groups: Sequence[tuple[str, Sequence[ExecutableBinding]]],
    *,
    inner_width: int,
    content_origin: tuple[int, int],
    content_width: int,
    viewport_height: int,
    scroll_offset: int,
    key_fg: tuple[int, int, int] | None = None,
    desc_fg: tuple[int, int, int] | None = None,
    show_cursor: bool = False,
) -> ViewportLayout:
    """Build viewport hit geometry from the same groups as the paint rows.

    Layout and paint share one wrap implementation
    (:func:`build_binding_browser_lines`), so click mapping can never drift
    from what is rendered.

    ``BindingBrowser`` derives its layout directly from ``_render`` (see
    ``BindingBrowser._rebuild_layout``); this helper is for ``HelpPanel``
    migration and unit tests. Callers must pass ``show_cursor=True`` to match
    the browser's paint — the default hides the cursor column and shifts hits.
    """
    lines = build_binding_browser_lines(
        groups,
        inner_width=inner_width,
        key_fg=key_fg,
        desc_fg=desc_fg,
        show_cursor=show_cursor,
    )
    return build_viewport_layout(
        [sel for _segs, sel in lines],
        content_origin=content_origin,
        content_width=content_width,
        viewport_height=viewport_height,
        scroll_offset=scroll_offset,
    )


def format_binding_group_rows(
    groups: Sequence[tuple[str, Sequence[ExecutableBinding]]],
    *,
    inner_width: int = 72,
    key_fg: tuple[int, int, int] | None = None,
    desc_fg: tuple[int, int, int] | None = None,
    show_cursor: bool = False,
) -> list[list[Segment]]:
    """Format binding groups as flat TextBrowser rows."""
    lines = build_binding_browser_lines(
        groups,
        inner_width=inner_width,
        key_fg=key_fg,
        desc_fg=desc_fg,
        show_cursor=show_cursor,
    )
    return [segments for segments, _sel in lines]
