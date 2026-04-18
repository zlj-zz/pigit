# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_layer.py
Description: Layer-based overlay stack for multi-level modal/toast/sheet support.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from pigit.termui._surface import Surface

from pigit.termui.types import LayerKind, OverlayDispatchResult


_VISIBLE_LAYER_KINDS = (LayerKind.TOAST, LayerKind.SHEET, LayerKind.MODAL)

_LOG = logging.getLogger(__name__)


class Layer:
    def __init__(self, kind: LayerKind) -> None:
        self.kind = kind
        self._stack: list[object] = []

    def push(self, surface: object) -> None:
        self._stack.append(surface)

    def pop(self) -> Optional[object]:
        if not self._stack:
            return None
        return self._stack.pop()

    def top(self) -> Optional[object]:
        if not self._stack:
            return None
        return self._stack[-1]

    def clear(self) -> None:
        """Remove all surfaces from this layer. Lifecycle (hide/reset) is caller's responsibility."""
        self._stack.clear()

    def is_empty(self) -> bool:
        return not self._stack

    def __iter__(self):
        return iter(self._stack)


class LayerStack:
    """
    Multi-layer overlay manager.
    Not a Component itself; held by ComponentRoot.
    """

    def __init__(self) -> None:
        self._layers = {
            LayerKind.TOAST: Layer(LayerKind.TOAST),
            LayerKind.SHEET: Layer(LayerKind.SHEET),
            LayerKind.MODAL: Layer(LayerKind.MODAL),
        }

    def push(self, kind: LayerKind, surface: object) -> None:
        self._layers[kind].push(surface)

    def pop(self, kind: LayerKind) -> Optional[object]:
        return self._layers[kind].pop()

    def top(self, kind: LayerKind) -> Optional[object]:
        return self._layers[kind].top()

    def is_empty(self, kind: LayerKind) -> bool:
        return self._layers[kind].is_empty()

    def has_any_open(self) -> bool:
        return any(not layer.is_empty() for layer in self._layers.values())

    def render(self, surface: "Surface") -> None:
        for kind in _VISIBLE_LAYER_KINDS:
            for overlay in self._layers[kind]:
                if getattr(overlay, "open", False):
                    overlay._render_surface(surface)

    def resize(self, size: tuple[int, int]) -> None:
        for kind in _VISIBLE_LAYER_KINDS:
            for overlay in self._layers[kind]:
                if hasattr(overlay, "resize"):
                    overlay.resize(size)

    def dispatch(self, key: str) -> OverlayDispatchResult:
        """Route key to top overlay. MODAL intercepts everything; SHEET/TOAST passthrough if dropped."""
        # MODAL intercepts everything
        modal = self._layers[LayerKind.MODAL]
        if not modal.is_empty():
            top = modal.top()
            if top is not None:
                try:
                    return top.dispatch_overlay_key(key)
                except Exception:
                    _LOG.exception("Overlay dispatch failed for key %r", key)
                    # Error recovery: close modal and clean up
                    modal.pop()
                    if hasattr(top, "hide"):
                        top.hide()
                    if hasattr(top, "reset_state"):
                        top.reset_state()
                    return OverlayDispatchResult.CLOSED_AFTER_ERROR

        # SHEET / TOAST: dispatch to top, passthrough if dropped
        for kind in (LayerKind.SHEET, LayerKind.TOAST):
            top = self._layers[kind].top()
            if top is not None and getattr(top, "open", False):
                result = top.dispatch_overlay_key(key)
                if result != OverlayDispatchResult.DROPPED_UNBOUND:
                    return result
                continue

        return OverlayDispatchResult.DROPPED_UNBOUND
