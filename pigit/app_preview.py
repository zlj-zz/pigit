"""
Module: pigit/app_preview.py
Description: Preview panel for Adaptive Split layout (large screens).
Author: Zev
Date: 2026-05-26
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Callable

from pigit.termui import EVT_SELECTION_CHANGED, Component, palette
from pigit.termui._component import _render_child_to_surface
from pigit.termui.wcwidth_table import wcswidth

from .app_diff import DiffType, DiffViewer
from .app_theme import THEME

if TYPE_CHECKING:
    from .viewmodels.status import IStatusViewModel


class PreviewPanel(Component):
    """Right-side preview panel showing diff or details for the current selection.

    Used in large-screen Adaptive Split layout alongside TabView.
    Renders a title bar + horizontal separator + diff content via DiffViewer.
    """

    TITLE_ROWS = 2  # title line + separator

    def __init__(
        self,
        *,
        status_vm: IStatusViewModel | None = None,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)
        self._status_vm = status_vm
        self._title = "Preview"
        self._subtitle = ""
        self._diff_viewer = DiffViewer(x=self.TITLE_ROWS + 1, y=1, id="preview_diff")
        self._unsubs: list[Callable[[], None]] = []

    def activate(self) -> None:
        """Activate the preview and its internal diff viewer."""
        super().activate()
        self._diff_viewer.activate()
        self._unsubs.append(self.subscribe(EVT_SELECTION_CHANGED, self._on_selection))

    def deactivate(self) -> None:
        """Deactivate the preview and its internal diff viewer."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._diff_viewer.deactivate()
        super().deactivate()

    def _on_selection(self, *, active: Component | None = None, **_) -> bool:
        """Update preview content for the active Status or Stash panel."""
        from .app_status import StatusPanel, _status_label
        from .app_stash import StashPanel

        if not isinstance(active, (StatusPanel, StashPanel)):
            self.clear()
            return True
        if self._status_vm is None:
            self.clear()
            return True

        if isinstance(active, StatusPanel):
            if (
                not active.files
                or active.curr_no < 0
                or active.curr_no >= len(active.files)
            ):
                self.clear()
                return True
            f = active.files[active.curr_no]
            source_idx = active.filter_source_index()
            diff_lines = self._status_vm.load_diff(source_idx)
            diff_type = (
                DiffType.STAGED
                if (f.has_staged_change and not f.has_unstaged_change)
                else DiffType.UNSTAGED
            )
            self.set_diff_type(diff_type)
            self.set_preview(diff_lines, title=f.name, subtitle=_status_label(f))
        elif isinstance(active, StashPanel):
            if (
                not active.stashes
                or active.curr_no < 0
                or active.curr_no >= len(active.stashes)
            ):
                self.clear()
                return True
            stash = active.stashes[active.curr_no]
            diff_lines = self._status_vm.load_stash_diff(stash.ref)
            self.set_diff_type(DiffType.STASH)
            self.set_preview(diff_lines, title=stash.msg, subtitle=stash.ref)
        return True

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
                fg=THEME.fg_branch_name,
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
                )

        # Horizontal separator (row 1)
        if h > 1:
            sep = "─" * w
            surface.draw_text_rgb(
                1,
                0,
                sep,
                fg=THEME.fg_dim,
            )

        # Diff content (rows 2+)
        if h > self.TITLE_ROWS:
            _render_child_to_surface(self._diff_viewer, surface, "PreviewPanel")
