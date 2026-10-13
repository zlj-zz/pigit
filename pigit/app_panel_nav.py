"""
Module: pigit/app_panel_nav.py
Description: Panel ring navigation for Status, Stash, Branch, Commit, and Graph tabs.
Author: Zev
Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Callable

from pigit.app_branch import BranchPanel
from pigit.app_commit import CommitPanel
from pigit.app_graph_panel import ContributionPanel
from pigit.app_stash import StashPanel
from pigit.app_status import StatusPanel
from pigit.termui import Component
from pigit.termui.containers import TabView


class PanelNavigator:
    """Cycle and goto helpers for the main panels.

    Ring index is derived from the product TabView (never Diff detail focus).
    """

    def __init__(
        self,
        *,
        get_tab_view: Callable[[], TabView],
        get_status_panel: Callable[[], StatusPanel],
        get_stash_panel: Callable[[], StashPanel],
        get_branch_panel: Callable[[], BranchPanel],
        get_commit_panel: Callable[[], CommitPanel],
        get_graph_panel: Callable[[], ContributionPanel],
        get_worktree_busy: Callable[[], bool],
    ) -> None:
        self._get_tab_view = get_tab_view
        self._get_status_panel = get_status_panel
        self._get_stash_panel = get_stash_panel
        self._get_branch_panel = get_branch_panel
        self._get_commit_panel = get_commit_panel
        self._get_graph_panel = get_graph_panel
        self._get_worktree_busy = get_worktree_busy

    def panel_ring(self) -> tuple[Component, ...]:
        """Return the panels that Tab/Shift+Tab cycle through, in order."""
        return (
            self._get_status_panel(),
            self._get_stash_panel(),
            self._get_branch_panel(),
            self._get_commit_panel(),
            self._get_graph_panel(),
        )

    def ring_index(self) -> int | None:
        """Index in the panel ring from the product TabView (ignore Diff detail)."""
        active = self._get_tab_view().visible
        if active is None:
            return None
        for idx, panel in enumerate(self.panel_ring()):
            if active is panel:
                return idx
        return None

    def focus_destination(self, panel: Component) -> None:
        """Route the product TabView to *panel*.

        Refused, silently, while a working-tree rewrite is in flight: arriving
        at a panel mounts it, and Status reads the worktree the moment it
        appears -- the half-applied state the observe defer already refuses to
        poll for. ``cycle_panel`` comes through here too, so both the number
        keys and Tab are covered by the one check.
        """
        if self._get_worktree_busy():
            return
        self._get_tab_view().route_to(panel.id)

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
            "graph": self._get_graph_panel(),
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
