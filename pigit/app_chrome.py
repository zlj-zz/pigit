"""
Module: pigit/app_chrome.py
Description: Application chrome components (header, footer).
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from pigit.termui import (
    EventType,
    EVT_SELECTION_CHANGED,
    by_id,
    Component,
    resolve_presentation_leaf,
)
from pigit.termui._runtime_context import get_overlay_host
from pigit.termui.component import collect_overlay_footer_entries
from pigit.termui.containers import TabView
from pigit.termui.widgets import Footer

from .app_theme import PigitTheme


class AppFooter(Footer):
    """Application footer that syncs help entries from the active panel."""

    def __init__(
        self,
        theme: PigitTheme,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        # Retained for API compatibility; colors resolve via get_theme() at render time.
        self._theme = theme

    def mount(self) -> None:
        super().mount()
        self.subscribe(EVT_SELECTION_CHANGED, self._sync_help)
        self.subscribe(EventType("mode_changed"), self._sync_help)

    def _sync_help(self, *, active: Component | None = None, **_) -> bool:
        if active is None:
            tab_view = by_id("tab_view", TabView)
            active = (
                resolve_presentation_leaf(tab_view.visible)
                if tab_view is not None
                else None
            )
        provider = getattr(active, "get_footer_entries", None) if active else None
        self.set_help_provider(provider)
        return True

    def _display_context(self) -> str:
        if self._presentation_overlay() is not None:
            return ""
        return super()._display_context()

    def _help_pairs(self) -> list[tuple[str, str]]:
        overlay = self._presentation_overlay()
        if overlay is not None:
            return collect_overlay_footer_entries(overlay)
        return super()._help_pairs()

    def _presentation_overlay(self) -> Component | None:
        host = get_overlay_host()
        if host is None:
            return None
        return host.presentation_overlay()
