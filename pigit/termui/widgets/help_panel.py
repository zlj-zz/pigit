"""
Module: pigit/termui/widgets/help_panel.py
Description: Help content panel (bordered, scrollable key list).
Author: Zev
Date: 2026-05-18
"""

from __future__ import annotations

from typing import Any, cast
from collections.abc import Callable

from .. import keys, palette
from .._component import Component
from .._frame import BoxFrame
from .._layout import Padding
from .._segment import Segment
from .._surface import Surface, _Subsurface
from ..wcwidth_table import truncate_by_width, wcswidth

HelpEntry = tuple[str, str]


class HelpPanel(Component):
    """
    Plain help content (bordered, scrollable key list). Not modal until wrapped.

    Wrap with :class:`~pigit.termui.widgets.popup.Popup` to make it modal.
    Bind ``?`` to a handler that refreshes rows (e.g.
    :meth:`refresh_entries_from_source`) when opening help, then calls
    ``popup.toggle()``.
    """

    BINDINGS = [
        (keys.KEY_DOWN, "scroll_down"),
        (keys.KEY_UP, "scroll_up"),
        ("j", "scroll_down"),
        ("k", "scroll_up"),
        ("?", "toggle"),
    ]

    def __init__(
        self,
        inner_width: int | None = None,
        inner_height: int | None = None,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        *,
        entries_source: Component | None = None,
        key_fg: tuple[int, int, int] | None = None,
        on_toggle: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(x=x, y=y, size=size)
        self._inner_w_cfg = inner_width
        self._inner_h_cfg = inner_height
        self._entries_source = entries_source
        self._key_fg = key_fg
        self._on_toggle = on_toggle
        self._lines: list[str] = []
        self._offset = 0
        self._inner_w = 40
        self._scroll_h = 6
        self._outer_w = 42
        self.outer_row_count = 10
        self._frame = BoxFrame(
            0, 0, title="Help   esc close", fg=palette.DEFAULT_FG, bg=palette.DEFAULT_BG
        )
        self._padding = Padding(top=2, right=4, bottom=2, left=4)
        self._line_segments: list[list[Segment]] = []

    def resize(self, size: tuple[int, int]) -> None:
        """Recalculate inner and outer dimensions for the given terminal size."""
        tw, th = int(size[0]), int(size[1])
        avail_w, avail_h = self._padding.apply((tw, th))
        inner_w = (
            self._inner_w_cfg if self._inner_w_cfg is not None else max(24, tw // 2)
        )
        inner_h = (
            self._inner_h_cfg if self._inner_h_cfg is not None else max(8, th // 2)
        )
        inner_w = max(16, min(inner_w, avail_w))
        inner_h = max(5, min(inner_h, avail_h))
        self._inner_w = inner_w
        self._scroll_h = max(1, inner_h - 1)
        self._frame.set_inner_size(self._inner_w, self._scroll_h)
        self._outer_w = self._frame.outer_width
        self.outer_row_count = self._frame.outer_height
        super().resize(size)

    def set_entries(self, entries: list[HelpEntry]) -> None:
        """Set flat help entries and rebuild rendered lines."""
        if not entries:
            self._lines = []
            self._line_segments = []
            self._offset = 0
            return
        max_key_w = max(wcswidth(key_disp) for key_disp, _ in entries)
        lines: list[str] = []
        segments: list[list[Segment]] = []
        for key_disp, desc in entries:
            pad = max_key_w - wcswidth(key_disp)
            line = f"{key_disp}{' ' * pad}  {desc}"
            lines.append(line)
            seg: list[Segment] = []
            if self._key_fg is not None:
                seg.append(Segment(key_disp, fg=self._key_fg))
                seg.append(Segment(" " * pad + "  "))
            else:
                seg.append(Segment(key_disp + " " * pad + "  "))
            seg.append(Segment(desc))
            segments.append(seg)
        self._lines = lines
        self._line_segments = segments
        self._offset = 0

    def set_grouped_entries(self, groups: list[tuple[str, list[HelpEntry]]]) -> None:
        """Set grouped help entries with category headers and rebuild rendered lines."""
        if not groups:
            self._lines = []
            self._line_segments = []
            self._offset = 0
            return
        max_key_w = 0
        for _, entries in groups:
            for key_disp, _ in entries:
                max_key_w = max(max_key_w, wcswidth(key_disp))

        lines: list[str] = []
        segments: list[list[Segment]] = []
        for title, entries in groups:
            if not entries:
                continue
            lines.append(title)
            segments.append([Segment(title, style_flags=palette.STYLE_BOLD)])
            for key_disp, desc in entries:
                pad = max_key_w - wcswidth(key_disp)
                line = f"  {key_disp}{' ' * pad}  {desc}"
                lines.append(line)
                seg: list[Segment] = []
                seg.append(Segment("  "))
                if self._key_fg is not None:
                    seg.append(Segment(key_disp, fg=self._key_fg))
                    seg.append(Segment(" " * pad + "  "))
                else:
                    seg.append(Segment(key_disp + " " * pad + "  "))
                seg.append(Segment(desc))
                segments.append(seg)
            lines.append("")
            segments.append([])

        self._lines = lines
        self._line_segments = segments
        self._offset = 0

    def on_before_show(self) -> None:
        """Refresh help entries from the configured source before opening."""
        if self._entries_source is not None:
            self.refresh_entries_from_source(self._entries_source)

    def refresh_entries_from_source(
        self, entries_source: Any, *, max_rows: int = 256
    ) -> None:
        """
        Build grouped help rows from ``entries_source.children``.

        Collect :meth:`~pigit.termui._component.Component.get_help_entries` from
        each mapped child, group by
        :meth:`~pigit.termui._component.Component.get_help_title`, then call
        :meth:`set_grouped_entries` (truncated to ``max_rows``).
        """
        children = getattr(entries_source, "children", None)
        if children is None:
            raise TypeError("Source must expose a non-optional `children` sequence.")
        groups: list[tuple[str, list[HelpEntry]]] = []
        for panel in children:
            entries = panel.get_help_entries()
            if not entries:
                continue
            title_getter = getattr(panel, "get_help_title", None)
            if callable(title_getter):
                title = cast(str, title_getter())
            else:
                title = panel.__class__.__name__.replace("Panel", "")
            groups.append((title, entries))
        self.set_grouped_entries(groups)

    def scroll_down(self) -> None:
        """Scroll the help content down by one line."""
        max_off = max(0, len(self._lines) - self._scroll_h)
        self._offset = min(self._offset + 1, max_off)

    def scroll_up(self) -> None:
        """Scroll the help content up by one line."""
        self._offset = max(0, self._offset - 1)

    def set_on_toggle(self, cb: Callable[[], None] | None) -> None:
        """Set the callback invoked by :meth:`toggle`."""
        self._on_toggle = cb

    def toggle(self) -> None:
        """Delegate toggle to the wrapping popup shell, if any."""
        if self._on_toggle is not None:
            self._on_toggle()

    def refresh(self) -> None:
        """No-op refresh for compatibility."""

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        surface.fill_rect_rgb(
            self.x, self.y, self._outer_w, self.outer_row_count, palette.DEFAULT_BG
        )
        self._frame.draw_onto(surface, self.x, self.y)

        content_row = self.x + 1
        content_col = self.y + 1
        chunk = self._line_segments[self._offset : self._offset + self._scroll_h]
        for i, segments in enumerate(chunk):
            row = content_row + i
            x = content_col
            for seg in segments:
                text = seg.text
                text_w = wcswidth(text)
                avail = content_col + self._inner_w - x
                if text_w > avail:
                    text = truncate_by_width(text, avail)
                surface.draw_text_rgb(
                    row,
                    x,
                    text,
                    fg=seg.fg,
                    bg=seg.bg,
                    style_flags=seg.style_flags,
                )
                x += wcswidth(text)
            if x < content_col + self._inner_w:
                surface.fill_rect_rgb(
                    row, x, content_col + self._inner_w - x, 1, palette.DEFAULT_BG
                )
