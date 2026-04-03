# -*- coding: utf-8 -*-
"""
Module: pigit/termui/overlay_host.py
Description: Reusable single-slot popup session for a Container-style loop root.
Author: Project Team
Date: 2026-04-01
"""

from __future__ import annotations

from typing import Optional

from pigit.termui.overlay_controller import OverlayController
from pigit.termui.overlay_kinds import (
    OverlayDispatchResult,
    OverlayKind,
    OverlaySurface,
)


class OverlayHostMixin:
    """
    Modal host for one :class:`~pigit.termui.components_overlay.Popup` at a time.

    **Contract**: mix only into a :class:`~pigit.termui.components.Container` subclass.
    ``overlay_kind`` is only :data:`~pigit.termui.overlay_kinds.OverlayKind.NONE` or
    :data:`~pigit.termui.overlay_kinds.OverlayKind.POPUP`; ``_active_popup`` holds the shell.

    A help :class:`~pigit.termui.components_overlay.Popup` wrapping :class:`~pigit.termui.components_overlay.HelpPanel`
    should be constructed with ``session_owner=self`` (or another component that resolves
    to this host) so the shell coordinates
    :meth:`begin_popup_session` / :meth:`end_popup_session`. :class:`~pigit.termui.components_overlay.AlertDialog`
    manages its own session in :meth:`~pigit.termui.components_overlay.AlertDialog.alert` / ``_finish_alert``.
    """

    def _init_overlay_host_state(self) -> None:
        self.overlay_kind = OverlayKind.NONE
        self._overlay_controller = OverlayController()
        self._active_popup: Optional[OverlaySurface] = None

    def begin_popup_session(self, popup: OverlaySurface) -> None:
        """Mark ``popup`` as the modal shell consuming input until :meth:`end_popup_session`."""

        self.overlay_kind = OverlayKind.POPUP
        self._active_popup = popup

    def end_popup_session(self) -> None:
        """Release the modal slot (idempotent if already ``NONE``)."""

        self.overlay_kind = OverlayKind.NONE
        self._active_popup = None

    def has_overlay_open(self) -> bool:
        return self.overlay_kind != OverlayKind.NONE

    def try_dispatch_overlay(self, key: str) -> OverlayDispatchResult:
        return self._overlay_controller.dispatch(self, key)

    def force_close_overlay_after_error(self) -> None:
        self.overlay_kind = OverlayKind.NONE
        ap = self._active_popup
        if ap is not None:
            ap.hide()
            reset = getattr(ap, "reset_state", None)
            if callable(reset):
                reset()
        self._active_popup = None

    def _render_termui_overlays(self) -> None:
        if self.overlay_kind != OverlayKind.POPUP:
            return
        ap = self._active_popup
        if ap is not None and getattr(ap, "open", False):
            ap._render()
