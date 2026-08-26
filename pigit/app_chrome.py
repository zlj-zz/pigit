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
