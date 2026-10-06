"""
Module: pigit/app_graph_panel.py
Description: Contribution heatmap as a standalone Graph tab panel.
Author: Zev
Date: 2026-10-06
"""

from __future__ import annotations

from collections.abc import Callable

from pigit.termui import Component, Surface, bind_signals, request_render

from .app_contribution_graph import ContributionGraph
from .viewmodels.commit import ICommitViewModel


class ContributionPanel(Component):
    """The contribution heatmap, given a whole tab instead of a footer band.

    As a band it only appeared on panels taller than 19 rows; a tab is always
    reachable. The cost is that it no longer sits in the corner of your eye
    while you read commits — a deliberate trade.

    It subscribes to ``commit_vm.items`` and never runs git itself.
    """

    TAB_NAME = "Graph"
    tab_key = "5"

    def __init__(self, *, vm: ICommitViewModel, id: str | None = None) -> None:
        super().__init__(id=id)
        self._vm = vm
        self._graph = ContributionGraph()
        # Commits already counted, for the append check in ``_extends_current``.
        self._commits: list = []
        self._vm_unsubs: list[Callable[[], None]] = []

    def paint(self, surface: Surface) -> None:
        """Draw the heatmap sized to this panel."""
        self._graph.resize((surface.width, surface.height))
        self._graph.paint(surface)

    def handle_mouse(self, event) -> bool:
        """Forward wheel events so the graph can pan horizontally."""
        return self._graph.handle_mouse(event)

    def mount(self) -> None:
        super().mount()
        self._bind_vm_signals()
        # Signals only fire on change: a stream that finished while this panel
        # was unmounted must be replayed, or the graph stays blank.
        if self._vm.items.value:
            self._on_items_changed()

    def unmount(self) -> None:
        super().unmount()
        self._unbind_vm_signals()

    def set_vm(self, vm: ICommitViewModel) -> None:
        """Retarget this panel to a new Commit ViewModel (repo session switch).

        Session owns VM lifetime; this only rebinds signals and reloads.
        """
        self._unbind_vm_signals()
        self._vm = vm
        self._commits = []
        self._graph.set_commits([])
        if self.is_mounted():
            self._bind_vm_signals()
            self._on_items_changed()

    def _unbind_vm_signals(self) -> None:
        """Drop subscriptions to the current ViewModel (if any)."""
        for unsub in self._vm_unsubs:
            unsub()
        self._vm_unsubs.clear()

    def _bind_vm_signals(self) -> None:
        """Bind vm.items signal; safe to call multiple times (idempotent)."""
        if not self._vm_unsubs:
            self._vm_unsubs.append(
                bind_signals(self, self._vm.items, callback=self._on_items_changed)
            )

    def _on_items_changed(self) -> None:
        if not self.is_mounted():
            return
        commits = list(self._vm.items.value)
        if self._extends_current(commits):
            # Incremental: recounting the whole history per streamed batch costs
            # ~8x more, and the callback runs on the main thread.
            self._graph.add_commits(commits[len(self._commits) :])
        else:
            self._graph.set_commits(commits)
        self._commits = commits
        request_render()

    def _extends_current(self, commits: list) -> bool:
        """True when *commits* only adds to what is already counted.

        Length alone is not enough: the stream's first batch *replaces*
        ``vm.items`` rather than appending to it, so re-pinning to a longer ref
        grows the list while swapping every entry. Comparing identity catches
        both — a replaced list fails on its first element. Nothing counted yet
        is a rebuild by definition.
        """
        current = self._commits
        return (
            bool(current)
            and len(commits) > len(current)
            and all(new is old for new, old in zip(commits, current))
        )
