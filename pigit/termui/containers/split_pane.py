"""
Module: pigit/termui/containers/split_pane.py
Description: Master/detail horizontal split with attach-detach lifecycle.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from .._component import Component
from .._layout import layout_flex

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .._surface import Surface, _Subsurface


class SplitPane(Component):
    """Horizontal master/detail split that owns attach, detach, and widths.

    Shows only the master when the terminal is narrow, detail is unwanted,
    or no detail component is set. Otherwise lays out master and detail with
    a fixed master column width derived from terminal columns.
    """

    def __init__(
        self,
        master: Component,
        detail: Component | None = None,
        *,
        breakpoint_cols: int = 120,
        master_ratio: float = 0.35,
        min_master: int = 50,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._master = master
        self._detail = detail
        self._breakpoint_cols = breakpoint_cols
        self._master_ratio = master_ratio
        self._min_master = min_master
        self._detail_wanted = True
        self._last_cols: int | None = None
        self._widths: list[int | Literal["flex"]] = ["flex"]
        self._last_child_ids: tuple[int, ...] | None = None
        self.children = [master]
        master.parent = self

    def set_detail(self, detail: Component | None) -> None:
        """Replace the detail component without changing the wanted flag."""
        self._detail = detail

    def set_detail_wanted(self, wanted: bool) -> None:
        """Set whether the detail pane should be shown when space allows."""
        self._detail_wanted = wanted

    def toggle_detail(self) -> None:
        """Flip detail visibility and re-apply the last known terminal width."""
        self._detail_wanted = not self._detail_wanted
        if self._last_cols is not None:
            self.apply_terminal_width(self._last_cols)

    def apply_terminal_width(self, cols: int) -> None:
        """Attach or detach detail and set horizontal widths from *cols*."""
        self._last_cols = cols
        show_detail = (
            cols >= self._breakpoint_cols
            and self._detail_wanted
            and self._detail is not None
        )
        if show_detail:
            master_w = max(self._min_master, int(cols * self._master_ratio))
            detail_w = max(1, cols - master_w)
            desired = [self._master, self._detail]
            widths: list[int | Literal["flex"]] = [master_w, detail_w]
        else:
            desired = [self._master]
            widths = ["flex"]
        self._sync_children(desired)
        self._apply_widths(widths)

    def activate(self) -> None:
        super().activate()
        for child in self.children:
            child.activate()

    def deactivate(self) -> None:
        super().deactivate()
        for child in self.children:
            child.deactivate()

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the pane and lay out attached children horizontally."""
        self._size = size
        width, height = size
        widths = layout_flex(self._widths, width)
        offset_h = 0
        for child, w in zip(self.children, widths, strict=True):
            child.x = 1
            child.y = offset_h + 1
            if w > 0:
                child.resize((w, height))
            _logger.debug(
                "SplitPane resize: child=%s x=%s y=%s size=%s",
                type(child).__name__,
                child.x,
                child.y,
                child._size,
            )
            offset_h += w

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        for child in self.children:
            w, h = child._size
            if w <= 0 or h <= 0:
                continue
            if child.x < 1 or child.y < 1:
                continue
            child._render_surface(
                surface.subsurface(max(0, child.x - 1), max(0, child.y - 1), w, h)
            )

    def _sync_children(self, desired: list[Component]) -> None:
        """Attach or detach children to match *desired*."""
        desired_set = set(desired)
        for child in list(self.children):
            if child not in desired_set:
                child.deactivate()
                self.children.remove(child)
                if child.parent is self:
                    child.parent = None
        for child in desired:
            if child not in self.children:
                self.children.append(child)
                child.parent = self
                child.activate()

    def _apply_widths(self, widths: list[int | Literal["flex"]]) -> None:
        """Update width spec and relayout when children or widths changed."""
        child_ids = tuple(id(child) for child in self.children)
        if widths == self._widths and child_ids == self._last_child_ids:
            return
        self._widths = list(widths)
        self._last_child_ids = child_ids
        if self._size is not None:
            self.resize(self._size)
