# -*- coding: utf-8 -*-
"""
Module: pigit/termui/overlay_controller.py
Description: Delegates overlay keys to the active :class:`~pigit.termui.overlay_kinds.OverlaySurface` shell.
Author: Zev
Date: 2026-04-01
"""

from __future__ import annotations

import logging
from typing import Optional, Protocol

from pigit.termui.overlay_kinds import (
    OverlayDispatchResult,
    OverlayKind,
    OverlaySurface,
)


class OverlayDispatchHost(Protocol):
    """
    Structural type for the modal host passed to :meth:`OverlayController.dispatch`.

    In practice this is a :class:`~pigit.termui.overlay_host.OverlayHostMixin` instance
    (e.g. the Git TUI root): it owns ``overlay_kind``, ``_active_popup``, and error
    recovery on the active shell.
    """

    overlay_kind: OverlayKind
    _active_popup: Optional[OverlaySurface]

    def force_close_overlay_after_error(self) -> None: ...


class OverlayController:
    """
    Routes keys to ``host._active_popup`` via :meth:`~pigit.termui.overlay_kinds.OverlaySurface.dispatch_overlay_key`.

    Implementations (e.g. :class:`~pigit.termui.components_overlay.Popup`) try shell bindings, then the child's,
    then a modal fallback.
    """

    def dispatch(self, host: OverlayDispatchHost, key: str) -> OverlayDispatchResult:
        if host.overlay_kind != OverlayKind.POPUP:
            return OverlayDispatchResult.DROPPED_UNBOUND
        popup = host._active_popup
        if popup is None:
            return OverlayDispatchResult.DROPPED_UNBOUND
        try:
            return popup.dispatch_overlay_key(key)
        except Exception:
            logging.getLogger(__name__).exception(
                "Overlay dispatch failed for key %r", key
            )
            host.force_close_overlay_after_error()
            return OverlayDispatchResult.CLOSED_AFTER_ERROR
