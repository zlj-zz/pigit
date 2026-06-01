"""
Module: pigit/termui/widgets/help_panel.py
Description: Help content panel (bordered, scrollable key list).
Author: Zev
Date: 2026-05-18
"""

from __future__ import annotations

from collections.abc import Callable

from .. import keys, palette
from .._component import Component
from .._frame import BoxFrame
from .._layout import Padding
from .._segment import Segment
from .._surface import Surface, _Subsurface
from ..wcwidth_table import truncate_by_width, wcswidth

HelpEntry = tuple[str, str]


def _wrap_text(text: str, max_width: int) -> list[str]:
    """Wrap *text* into lines no wider than *max_width*.

    Breaks at word boundaries when possible; falls back to character
    boundaries for very long words.
    """
    if max_width <= 0:
        return [text]
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        if wcswidth(candidate) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            # If a single word is too long, break it forcibly
            if wcswidth(word) > max_width:
                for ch in word:
                    candidate2 = f"{current}{ch}" if current else ch
                    if wcswidth(candidate2) <= max_width:
                        current = candidate2
                    else:
                        if current:
                            lines.append(current)
                        current = ch
            else:
                current = word
    if current:
        lines.append(current)
    return lines if lines else [""]


class HelpPanel(Component):
    """
    Plain help content (bordered, scrollable key list). Not modal until wrapped.

    Wrap with :class:`~pigit.termui.widgets.popup.Popup` to make it modal.
    Content is set statically via :meth:`set_entries` or
    :meth:`set_grouped_entries`.

    Long descriptions are automatically wrapped to fit the panel width;
    continuation lines align with the first line's description column.

    Width is content-adaptive with a min/max cap so the panel is neither
    cramped in narrow terminals nor wastefully wide in large ones.
    """

    MIN_INNER_W = 58
    MAX_INNER_W = 108

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
        key_fg: tuple[int, int, int] | None = None,
        on_toggle: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(x=x, y=y, size=size)
        self._inner_w_cfg = inner_width
        self._inner_h_cfg = inner_height
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
        # Raw data for lazy rebuild on resize
        self._entries: list[HelpEntry] | None = None
        self._groups: list[tuple[str, list[HelpEntry]]] | None = None

    def _estimate_content_width(self) -> int:
        """Estimate minimum inner width needed by current content."""
        entries = self._entries
        groups = self._groups
        gap = 2
        group_indent = 2

        if groups:
            max_key_w = 0
            desc_lengths: list[int] = []
            for _, ents in groups:
                for key_disp, desc in ents:
                    max_key_w = max(max_key_w, wcswidth(key_disp))
                    desc_lengths.append(wcswidth(desc))
            avg_desc = sum(desc_lengths) // len(desc_lengths) if desc_lengths else 0
            desc_w = min(max(avg_desc, 16), 40)
            return group_indent + max_key_w + gap + desc_w

        if entries:
            max_key_w = max((wcswidth(k) for k, _ in entries), default=0)
            desc_lengths = [wcswidth(d) for _, d in entries]
            avg_desc = sum(desc_lengths) // len(desc_lengths) if desc_lengths else 0
            desc_w = min(max(avg_desc, 16), 40)
            return max_key_w + gap + desc_w

        return 0

    def resize(self, size: tuple[int, int]) -> None:
        """Recalculate inner and outer dimensions for the given terminal size."""
        tw, th = int(size[0]), int(size[1])
        avail_w, avail_h = self._padding.apply((tw, th))

        if self._inner_w_cfg is not None:
            inner_w = self._inner_w_cfg
        else:
            content_w = self._estimate_content_width()
            if content_w:
                inner_w = max(
                    self.MIN_INNER_W,
                    min(content_w, self.MAX_INNER_W, avail_w),
                )
            else:
                inner_w = max(self.MIN_INNER_W, min(self.MAX_INNER_W, avail_w))

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
        self._rebuild()

    # ------------------------------------------------------------------
    # Content setters
    # ------------------------------------------------------------------

    def set_entries(self, entries: list[HelpEntry]) -> None:
        """Set flat help entries and rebuild rendered lines."""
        self._entries = list(entries)
        self._groups = None
        self._rebuild()

    def set_grouped_entries(self, groups: list[tuple[str, list[HelpEntry]]]) -> None:
        """Set grouped help entries with category headers and rebuild rendered lines."""
        self._groups = list(groups)
        self._entries = None
        self._rebuild()

    # ------------------------------------------------------------------
    # Rebuild (wrap-aware)
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        """Rebuild _lines and _line_segments from raw data using current _inner_w."""
        if self._entries is not None:
            self._lines, self._line_segments = self._build_flat(self._entries)
        elif self._groups is not None:
            self._lines, self._line_segments = self._build_grouped(self._groups)
        else:
            self._lines = []
            self._line_segments = []
        self._offset = 0

    def _build_flat(
        self, entries: list[HelpEntry]
    ) -> tuple[list[str], list[list[Segment]]]:
        if not entries:
            return [], []
        max_key_w = max(wcswidth(key_disp) for key_disp, _ in entries)
        gap = 2  # space between key column and description
        desc_avail = max(1, self._inner_w - max_key_w - gap)

        lines: list[str] = []
        segments: list[list[Segment]] = []
        for key_disp, desc in entries:
            wrapped = _wrap_text(desc, desc_avail)
            for i, desc_line in enumerate(wrapped):
                if i == 0:
                    pad = max_key_w - wcswidth(key_disp)
                    line = f"{key_disp}{' ' * pad}{' ' * gap}{desc_line}"
                    seg: list[Segment] = []
                    if self._key_fg is not None:
                        seg.append(Segment(key_disp, fg=self._key_fg))
                        seg.append(Segment(" " * pad + " " * gap))
                    else:
                        seg.append(Segment(key_disp + " " * pad + " " * gap))
                    seg.append(Segment(desc_line))
                else:
                    indent = max_key_w + gap
                    line = f"{' ' * indent}{desc_line}"
                    seg = [Segment(" " * indent), Segment(desc_line)]
                lines.append(line)
                segments.append(seg)
        return lines, segments

    def _build_grouped(
        self, groups: list[tuple[str, list[HelpEntry]]]
    ) -> tuple[list[str], list[list[Segment]]]:
        if not groups:
            return [], []
        max_key_w = 0
        for _, entries in groups:
            for key_disp, _ in entries:
                max_key_w = max(max_key_w, wcswidth(key_disp))

        group_indent = 2
        gap = 2
        desc_avail = max(1, self._inner_w - group_indent - max_key_w - gap)

        lines: list[str] = []
        segments: list[list[Segment]] = []
        for title, entries in groups:
            if not entries:
                continue
            lines.append(title)
            segments.append([Segment(title, style_flags=palette.STYLE_BOLD)])
            for key_disp, desc in entries:
                wrapped = _wrap_text(desc, desc_avail)
                for i, desc_line in enumerate(wrapped):
                    if i == 0:
                        pad = max_key_w - wcswidth(key_disp)
                        line = f"{' ' * group_indent}{key_disp}{' ' * pad}{' ' * gap}{desc_line}"
                        seg: list[Segment] = []
                        seg.append(Segment(" " * group_indent))
                        if self._key_fg is not None:
                            seg.append(Segment(key_disp, fg=self._key_fg))
                            seg.append(Segment(" " * pad + " " * gap))
                        else:
                            seg.append(Segment(key_disp + " " * pad + " " * gap))
                        seg.append(Segment(desc_line))
                    else:
                        indent = group_indent + max_key_w + gap
                        line = f"{' ' * indent}{desc_line}"
                        seg = [Segment(" " * indent), Segment(desc_line)]
                    lines.append(line)
                    segments.append(seg)
            lines.append("")
            segments.append([])

        return lines, segments

    # ------------------------------------------------------------------
    # Scrolling
    # ------------------------------------------------------------------

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
