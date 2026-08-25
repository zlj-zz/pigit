"""
Module: pigit/app_panel_nav.py
Description: Panel ring navigation for Status, Stash, Branch, and Commit tabs.
Author: Zev
Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Callable

from pigit.app_branch import BranchPanel
from pigit.app_commit import CommitPanel
from pigit.app_stash import StashPanel
from pigit.app_status import StatusPanel
from pigit.termui import Component, resolve_presentation_leaf
from pigit.termui.containers import Column, TabView


class PanelNavigator:
    """Cycle and goto helpers for the four main list panels.

    Ring index is derived from the product TabView (never Diff detail focus).
    """

    def __init__(
        self,
        *,
        get_tab_view: Callable[[], TabView],
        get_status_stack: Callable[[], Column],
        get_status_panel: Callable[[], StatusPanel],
        get_stash_panel: Callable[[], StashPanel],
        get_branch_panel: Callable[[], BranchPanel],
        get_commit_panel: Callable[[], CommitPanel],
    ) -> None:
        self._get_tab_view = get_tab_view
        self._get_status_stack = get_status_stack
        self._get_status_panel = get_status_panel
        self._get_stash_panel = get_stash_panel
        self._get_branch_panel = get_branch_panel
        self._get_commit_panel = get_commit_panel

    def panel_ring(self) -> tuple[Component, ...]:
        """Return the four panels that Tab/Shift+Tab cycle through, in order."""
        return (
            self._get_status_panel(),
            self._get_stash_panel(),
            self._get_branch_panel(),
            self._get_commit_panel(),
        )

    def ring_index(self) -> int | None:
        """Index in the panel ring from the product TabView (ignore Diff detail)."""
        tab = self._get_tab_view()
        active = tab.active
        if active is self._get_status_stack():
            leaf = self._get_status_stack().focus_child
            if leaf is None:
                leaf = resolve_presentation_leaf(active)
        else:
            leaf = active
        if leaf is None:
            return None
        for idx, panel in enumerate(self.panel_ring()):
            if leaf is panel:
                return idx
        return None

    def focus_destination(self, panel: Component) -> None:
        """Move TabView + Status/Stash column focus to *panel*."""
        if panel is self._get_status_panel():
            self._get_tab_view().route_to("status")
            self._get_status_stack().set_focus_index(0)
            return
        if panel is self._get_stash_panel():
            self._get_tab_view().route_to("status")
            self._get_status_stack().set_focus_index(1)
            return
        if panel is self._get_branch_panel():
            self._get_tab_view().route_to("branch")
            return
        if panel is self._get_commit_panel():
            self._get_tab_view().route_to("commit")

    def resolve_panel(self, target: object) -> Component | None:
        """Map a ring panel identity or product id string to a ring panel."""
        for panel in self.panel_ring():
            if target is panel:
                return panel
        if not isinstance(target, str):
            return None
        by_id = {
            "status": self._get_status_panel(),
            "stash": self._get_stash_panel(),
            "branch": self._get_branch_panel(),
            "commit": self._get_commit_panel(),
        }
        return by_id.get(target)

    def cycle_panel(self, step: int) -> None:
        """Move focus ``step`` positions around the panel ring.

        No-op when the product tab is outside the ring.
        """
        idx = self.ring_index()
        if idx is None:
            return
        ring = self.panel_ring()
        self.focus_destination(ring[(idx + step) % len(ring)])
