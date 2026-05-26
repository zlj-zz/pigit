"""
Module: pigit/app_preview.py
Description: Preview panel for Adaptive Split layout (large screens).
Author: Zev
Date: 2026-05-26
"""

from __future__ import annotations

from pigit.termui import Component, palette
from pigit.termui._component import _render_child_to_surface
from pigit.termui.wcwidth_table import wcswidth

from .app_diff import DiffType, DiffViewer
from .app_theme import THEME


class PreviewPanel(Component):
    """Right-side preview panel showing diff or details for the current selection.

    Used in large-screen Adaptive Split layout alongside TabView.
    Renders a title bar + horizontal separator + diff content via DiffViewer.
    """

    TITLE_ROWS = 2  # title line + separator

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)
        self._title = "Preview"
        self._subtitle = ""
        self._diff_viewer = DiffViewer(x=self.TITLE_ROWS + 1, y=1, id="preview_diff")

    def set_preview(
        self, diff_lines: list[str], title: str, subtitle: str = ""
    ) -> None:
        """Load diff content and update title."""
        self._title = title
        self._subtitle = subtitle
        self._diff_viewer.set_content(diff_lines)

    def set_diff_type(self, diff_type: DiffType) -> None:
        """Set the diff type on the internal diff viewer."""
        self._diff_viewer.set_diff_type(diff_type)

    def clear(self) -> None:
        """Clear preview content."""
        self._title = "Preview"
        self._subtitle = ""
        self._diff_viewer.set_content([])

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        dv_w = max(1, size[0])
        dv_h = max(1, size[1] - self.TITLE_ROWS)
        self._diff_viewer.resize((dv_w, dv_h))

    def scroll_down(self, step: int = 1) -> None:
        """Scroll the internal diff viewer down."""
        self._diff_viewer.scroll_down(step)

    def scroll_up(self, step: int = 1) -> None:
        """Scroll the internal diff viewer up."""
        self._diff_viewer.scroll_up(step)

    def _render_surface(self, surface) -> None:
        w = surface.width
        h = surface.height
        if w <= 0 or h <= 0:
            return

        # Title bar (row 0)
        title_text = f" {self._title} "
        title_w = wcswidth(title_text)
        if title_w < w:
            surface.draw_text_rgb(
                0,
                0,
                title_text,
                fg=THEME.accent_cyan,
                bg=palette.DEFAULT_BG,
                style_flags=palette.STYLE_BOLD,
            )

        # Subtitle right-aligned
        if self._subtitle:
            sub_w = wcswidth(self._subtitle)
            sub_x = w - sub_w - 1
            if sub_x > title_w:
                surface.draw_text_rgb(
                    0,
                    sub_x,
                    self._subtitle,
                    fg=THEME.fg_dim,
                    bg=palette.DEFAULT_BG,
                )

        # Horizontal separator (row 1)
        if h > 1:
            sep = "─" * w
            surface.draw_text_rgb(
                1,
                0,
                sep,
                fg=THEME.fg_dim,
                bg=palette.DEFAULT_BG,
            )

        # Diff content (rows 2+)
        if h > self.TITLE_ROWS:
            _render_child_to_surface(self._diff_viewer, surface, "PreviewPanel")
