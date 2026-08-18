# -*- coding: utf-8 -*-
"""
Module: pigit/app_preview.py
Description: 大屏 Status/Stash 侧栏：把选中项的 diff 交给 DiffViewer。
Author: Zev
Date: 2026-05-26
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Callable

from pigit.termui import EVT_SELECTION_CHANGED, Component
from pigit.termui._component import _render_child_to_surface
from pigit.termui._mouse import MouseEvent

from .app_diff import DiffType, DiffViewer

if TYPE_CHECKING:
    from .viewmodels.status import IStatusViewModel


class PreviewPanel(Component):
    """Host that loads Status/Stash diffs into a full-size DiffViewer.

    Chrome is DiffViewer's own box; this panel only wires selection to content.
    """

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
        self._diff_viewer = DiffViewer(
            x=1,
            y=1,
            id="preview_diff",
            word_diff=True,
        )
        self._unsubs: list[Callable[[], None]] = []

    def activate(self) -> None:
        """Activate the inner diff viewer and subscribe to selection changes."""
        super().activate()
        self._diff_viewer.activate()
        self._unsubs.append(self.subscribe(EVT_SELECTION_CHANGED, self._on_selection))

    def deactivate(self) -> None:
        """Unsubscribe and deactivate the inner diff viewer."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._diff_viewer.deactivate()
        super().deactivate()

    def _on_selection(self, *, active: Component | None = None, **_) -> bool:
        """Update the inner DiffViewer for the active Status or Stash panel."""
        from .app_status import StatusPanel, _status_label
        from .app_stash import StashPanel

        if not isinstance(active, (StatusPanel, StashPanel)):
            self.clear()
            return True
        if self._status_vm is None:
            self.clear()
            return True

        if isinstance(active, StatusPanel):
            hit = active.file_at_cursor()
            if hit is None:
                self.clear()
                return True
            f, source_idx = hit
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
        """Load diff lines and put ``title`` / ``subtitle`` on the viewer's box."""
        label = title if not subtitle else f"{title}  {subtitle}"
        self._diff_viewer.set_box_title(label)
        self._diff_viewer.set_content(diff_lines)

    def set_diff_type(self, diff_type: DiffType) -> None:
        """Set the diff type on the inner viewer."""
        self._diff_viewer.set_diff_type(diff_type)

    def clear(self) -> None:
        """Clear the inner viewer."""
        self._diff_viewer.set_box_title("")
        self._diff_viewer.set_content([])

    def resize(self, size: tuple[int, int]) -> None:
        """Give the inner DiffViewer the full preview size."""
        self._size = size
        self._diff_viewer.x = 1
        self._diff_viewer.y = 1
        self._diff_viewer.resize(size)

    def scroll_down(self, step: int = 1) -> None:
        """Scroll the inner diff viewer down."""
        self._diff_viewer.scroll_down(step)

    def scroll_up(self, step: int = 1) -> None:
        """Scroll the inner diff viewer up."""
        self._diff_viewer.scroll_up(step)

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Wheel-scroll the inner diff; clicks are ignored (preview is not focused)."""
        return self._diff_viewer.handle_mouse(event)

    def _render_surface(self, surface) -> None:
        _render_child_to_surface(self._diff_viewer, surface, "PreviewPanel")
