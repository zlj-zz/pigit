# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_component_mixins.py
Description: Mixin classes for TUI components (lazy resize, overlay client).
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Any

from pigit.termui.types import ToastPosition

if TYPE_CHECKING:
    from pigit.termui.components import Component


class GitPanelLazyResizeMixin:
    """Defer expensive :meth:`fresh` until the panel is activated.

    Inactive panels show a one-line placeholder until first shown, so startup
    ``resize`` avoids running git for every tab. Pair with a container that
    calls :meth:`fresh` when switching to the active child (:meth:`TabView.switch_child`).
    """

    _panel_loaded: bool = False

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        if self.is_activated():
            self.fresh()
            self._panel_loaded = True
        elif not self._panel_loaded:
            self.set_content(["Loading..."])
            self.curr_no = 0
            self._r_start = 0


class OverlayClientMixin:
    """Mixin for components that trigger overlays (Toast/Sheet).

    Usage:
        class StatusPanel(Component, OverlayClientMixin):
            def on_key(self, key):
                if key == "i":
                    self.show_toast("File ignored", duration=2.0)
    """

    def _nearest_host_with(self, attr: str) -> Optional["Component"]:
        """Walk parent chain to find host with specified attribute."""
        current: Optional["Component"] = getattr(self, "parent", None)
        while current is not None:
            if hasattr(current, attr):
                return current
            current = current.parent
        return None

    def show_toast(
        self,
        message: str,
        *,
        duration: float = 2.0,
        position: Optional[ToastPosition] = None,
    ) -> Optional[Any]:
        """Show toast notification via nearest host.

        Args:
            message: Toast message content.
            duration: Display duration in seconds.
            position: ToastPosition enum value (None for default TOP_RIGHT).

        Returns:
            Toast instance if successful, None if no host found.
        """
        host = self._nearest_host_with("show_toast")
        if host is None:
            return None

        if position is None:
            position = ToastPosition.TOP_RIGHT
        return host.show_toast(message, duration=duration, position=position)

    def show_sheet(self, child: "Component", height: int = 8) -> Optional[Any]:
        """Show bottom sheet via nearest host.

        Args:
            child: Component to display in sheet.
            height: Sheet height in rows.

        Returns:
            Sheet instance if successful, None if no host found.
        """
        host = self._nearest_host_with("show_sheet")
        if host is None:
            return None
        return host.show_sheet(child, height)
