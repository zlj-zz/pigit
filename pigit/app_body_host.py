"""
Module: pigit/app_body_host.py
Description: Body layout host swapping product SplitPane and Diff detail without deactivate.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pigit.termui import (
    Component,
    EVT_SELECTION_CHANGED,
    get_focus_manager,
    render_child,
    request_render,
    resolve_presentation_leaf,
)
from pigit.termui.component import resolve_focus_leaf

if TYPE_CHECKING:
    from pigit.termui.surface import SurfaceView


class BodyHost(Component):
    """Single flex slot: product surface or Diff detail (hide ≠ deactivate).

    Both children stay activated for the app lifetime. Only the visible child
    is painted and receives focus / hit-testing.
    """

    def __init__(
        self,
        product: Component,
        detail: Component,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._product = product
        self._detail = detail
        self._detail_open = False
        self.children = [product, detail]
        for child in self.children:
            child.parent = self
        # Keep both alive; never deactivate on show swaps.
        product.activate()
        detail.activate()

    @property
    def product(self) -> Component:
        """Product surface (typically SplitPane + TabView)."""
        return self._product

    @property
    def detail(self) -> Component:
        """Detail surface (DiffViewer)."""
        return self._detail

    @property
    def is_detail_open(self) -> bool:
        """True when Diff detail occupies the body slot."""
        return self._detail_open

    @property
    def focus_child(self) -> Component | None:
        """Focus drills into the visible child only."""
        return self._visible()

    def show_detail(self) -> None:
        """Show Diff detail; do not deactivate the product subtree."""
        self._detail_open = True
        self._focus_visible()
        self.emit(
            EVT_SELECTION_CHANGED,
            active=resolve_presentation_leaf(self._detail),
        )
        request_render()

    def show_product(self) -> None:
        """Show product surface; pause Diff background work without deactivate."""
        self._detail_open = False
        pause = getattr(self._detail, "pause_background", None)
        if callable(pause):
            pause()
        self._focus_visible()
        self.emit(
            EVT_SELECTION_CHANGED,
            active=resolve_presentation_leaf(self._product),
        )
        request_render()

    def resize(self, size: tuple[int, int]) -> None:
        """Resize host and keep both children geometrically valid."""
        self._size = size
        self._product.resize(size)
        self._detail.resize(size)

    def _visible(self) -> Component:
        return self._detail if self._detail_open else self._product

    def _focus_visible(self) -> None:
        fm = get_focus_manager()
        if fm is None:
            return
        fm.set_focus_chain(resolve_focus_leaf(self._visible()))

    def _render_surface(self, surface: SurfaceView) -> None:
        render_child(self._visible(), surface, "BodyHost")

    def _handle_event(self, key: str) -> bool:
        return self._visible()._handle_event(key)

    def _hit_test(self, col: int, row: int) -> tuple[Component, int, int] | None:
        return self._visible()._hit_test(col, row)
