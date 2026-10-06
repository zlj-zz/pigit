"""
Module: pigit/app_graph_panel.py
Description: Graph tab — a board of self-contained commit graphs.
Author: Zev
Date: 2026-10-06
"""

from __future__ import annotations

from collections.abc import Callable

from pigit.termui import Component, Surface, bind_action, bind_signals, request_render
from pigit.termui.containers import FlowBoard
from pigit.termui.containers.flow_board import PAN_STEP

from .app_graph_blocks import AuthorChart, ContributionHeatmap
from .viewmodels.commit import ICommitViewModel


class ContributionPanel(Component):
    """Commit graphs on a board that wraps them to the width it is given.

    As a footer band this only appeared on panels taller than 19 rows; a tab is
    always reachable, and the board gives each graph the size it asks for
    instead of one layout with the geometry written into it.

    It subscribes to ``commit_vm.items`` and never runs git itself.
    """

    TAB_NAME = "Graph"
    tab_key = "5"
    keymap_namespace = "graph"

    def __init__(self, *, vm: ICommitViewModel, id: str | None = None) -> None:
        super().__init__(id=id)
        self._vm = vm
        self._heatmap = ContributionHeatmap()
        self._chart = AuthorChart()
        self._board = FlowBoard([self._heatmap, self._chart])
        # Commits already counted, for the append check in ``_extends_current``.
        self._commits: list = []
        self._vm_unsubs: list[Callable[[], None]] = []

    def mount(self) -> None:
        super().mount()
        self._board.mount()
        self._bind_vm_signals()
        # Signals only fire on change: a stream that finished while this panel
        # was unmounted must be replayed, or the graphs stay blank.
        if self._vm.items.value:
            self._on_items_changed()

    def unmount(self) -> None:
        self._board.unmount()
        super().unmount()
        self._unbind_vm_signals()

    def resize(self, size: tuple[int, int]) -> None:
        super().resize(size)
        self._board.resize(size)

    def paint(self, surface: Surface) -> None:
        self._board.paint(surface)

    def handle_mouse(self, event) -> bool:
        """Wheel events pan the board."""
        return self._board.handle_mouse(event)

    @bind_action("scroll_up", "k", "up", desc="Pan the graphs up", tip="Pan")
    def scroll_up(self) -> None:
        """Scroll the board up."""
        self._board.pan_by(rows=-PAN_STEP)

    @bind_action("scroll_down", "j", "down", desc="Pan the graphs down", tip="Pan")
    def scroll_down(self) -> None:
        """Scroll the board down."""
        self._board.pan_by(rows=PAN_STEP)

    @bind_action("scroll_left", "h", "left", desc="Pan the graphs left", tip="Pan")
    def scroll_left(self) -> None:
        """Scroll the board left."""
        self._board.pan_by(cols=-PAN_STEP)

    @bind_action("scroll_right", "l", "right", desc="Pan the graphs right", tip="Pan")
    def scroll_right(self) -> None:
        """Scroll the board right."""
        self._board.pan_by(cols=PAN_STEP)

    @bind_action("pan_home", "home", desc="Back to the first graph", tip="Origin")
    def pan_home(self) -> None:
        """Return the board to its origin."""
        self._board.pan_home()

    @bind_action("page_down", "ctrl d", desc="Pan the graphs half a screen down")
    def page_down(self) -> None:
        """Scroll the board down by half the window."""
        _, viewport_h = self._board.viewport_size
        self._board.pan_by(rows=max(1, viewport_h // 2))

    @bind_action("page_up", "ctrl u", desc="Pan the graphs half a screen up")
    def page_up(self) -> None:
        """Scroll the board up by half the window."""
        _, viewport_h = self._board.viewport_size
        self._board.pan_by(rows=-max(1, viewport_h // 2))

    def set_vm(self, vm: ICommitViewModel) -> None:
        """Retarget this panel to a new Commit ViewModel (repo session switch).

        Session owns VM lifetime; this only rebinds signals and reloads.
        """
        self._unbind_vm_signals()
        self._vm = vm
        self._commits = []
        self._heatmap.set_commits([])
        self._chart.set_commits([])
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
        # Decide once, then tell every block the same thing: recounting a whole
        # history per streamed batch costs ~8x more and runs on the main thread.
        added = commits[len(self._commits) :] if self._extends_current(commits) else None
        for block in (self._heatmap, self._chart):
            if added is None:
                block.set_commits(commits)
            else:
                block.add_commits(added)
        self._commits = commits
        request_render()

    def _extends_current(self, commits: list) -> bool:
        """True when *commits* only adds to what is already counted.

        Length alone is not enough: the stream's first batch *replaces*
        ``vm.items`` rather than appending to it, so re-pinning to a longer ref
        grows the list while swapping every entry. Comparing identity catches
        both — a replaced list fails on its first element.
        """
        current = self._commits
        return (
            bool(current)
            and len(commits) > len(current)
            and all(new is old for new, old in zip(commits, current))
        )
