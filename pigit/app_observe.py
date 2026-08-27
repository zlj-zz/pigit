"""
Module: pigit/app_observe.py
Description: Repo observation host with explicit ObserveDeps injection.
Author: Zev
Date: 2026-08-24
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from pigit.app_branch import BranchPanel
from pigit.app_commit import CommitPanel
from pigit.app_log_graph_preview import LogGraphPreview
from pigit.app_preview import PreviewPanel
from pigit.app_stash import StashPanel
from pigit.app_status import StatusPanel
from pigit.config_data import AppConfig
from pigit.git.api import GitApi, GitError
from pigit.observe import (
    ChangeBatch,
    ChangeKind,
    ObserveContext,
    RefreshCoordinator,
    RepoObserver,
    StatMtimeBackend,
    WatchRoot,
    should_defer_repo_refresh,
)
from pigit.observe.denylist import rel_path_is_denied
from pigit.observe.digest import hash_porcelain
from pigit.termui import Component, ComponentRoot, resolve_presentation_leaf
from pigit.termui.containers import TabView
from pigit.termui.event_loop import AppEventLoop
from pigit.viewmodels.status import StatusViewModel

# FS mtime poll cadence for StatMtimeBackend.
_OBSERVE_POLL_INTERVAL_S = 1.0
# UI queue drain / debounce flush retry cadence.
_OBSERVE_DRAIN_INTERVAL_S = 0.15


@dataclass(frozen=True)
class ObserveDeps:
    """Narrow dependencies for ObserveHost (no app back-reference).

    Attributes:
        get_git: Late-bound GitApi accessor.
        get_repo_path: Callable returning the repository root path.
        get_config: Callable returning AppConfig (observe flags).
        get_status_vm: Late-bound StatusViewModel accessor.
        get_tab_view: Late-bound TabView accessor.
        get_preview_panel: Late-bound PreviewPanel accessor (may be None).
        get_log_graph_preview: Late-bound LogGraphPreview accessor (may be None).
        get_diff_preview_wanted: Whether diff side preview is visible.
        get_log_graph_wanted: Whether log-graph side preview is visible.
        get_is_large_screen: Whether terminal width qualifies as large screen.
        get_root: Callable returning ComponentRoot (may be None pre-mount).
        get_loop: Callable returning the AppEventLoop (may be None pre-start).
        schedule_reload_header: Callback to async-reload header branch/ahead/behind.
        refresh_list_panel: Callback to refresh a list panel or its ViewModel.
    """

    get_git: Callable[[], GitApi]
    get_repo_path: Callable[[], str]
    get_config: Callable[[], AppConfig]
    get_status_vm: Callable[[], StatusViewModel]
    get_tab_view: Callable[[], TabView]
    get_preview_panel: Callable[[], PreviewPanel | None]
    get_log_graph_preview: Callable[[], LogGraphPreview | None]
    get_diff_preview_wanted: Callable[[], bool]
    get_log_graph_wanted: Callable[[], bool]
    get_is_large_screen: Callable[[], bool]
    get_root: Callable[[], ComponentRoot | None]
    get_loop: Callable[[], AppEventLoop | None]
    schedule_reload_header: Callable[[], None]
    refresh_list_panel: Callable[[Component], None]


class ObserveHost:
    """Start/stop repo observation, watch roots, and apply ChangeBatch updates.

    Attributes:
        deps: Injected ObserveDeps bundle.
    """

    def __init__(self, deps: ObserveDeps) -> None:
        """
        Args:
            deps: Narrow dependency bundle; git/vms resolved at call time.
        """
        self._deps = deps
        self._observer: RepoObserver | None = None
        self._coordinator: RefreshCoordinator | None = None
        self._observe_ctx: ObserveContext | None = None
        self._observe_poll_id: int | None = None
        self._observe_drain_id: int | None = None
        self._observe_status_unsub: Callable[[], None] | None = None
        self._last_worktree_dirty: bool | None = None
        # True only while a worktree root is actually attached (Status tab
        # focused); digest values from other tabs are stale and must not be
        # reused for the header dirty dot.
        self._worktree_watched = False

    def start(self) -> None:
        """Start StatMtime observation of git metadata (and Status worktree)."""
        git = self._deps.get_git()
        try:
            git_dir = git.get_git_dir()
            common_dir = git.get_git_common_dir()
        except GitError:
            logging.warning(
                "Repo observe disabled: cannot resolve git dirs", exc_info=True
            )
            return
        repo_root = self._deps.get_repo_path() or ""
        self._observe_ctx = ObserveContext(
            repo_root=repo_root,
            git_dir=git_dir,
            common_dir=common_dir,
        )
        backend = StatMtimeBackend(worktree_digest=self._worktree_digest)
        observer = RepoObserver(backend=backend)
        self._observer = observer
        self._coordinator = RefreshCoordinator(
            observer.queue,
            defer_fn=lambda: should_defer_repo_refresh(self._deps.get_root()),
            on_batch=self.on_batch,
            ctx_provider=self._context,
        )
        self.resync_roots(reset=True)
        if self._observe_status_unsub is None:
            self._observe_status_unsub = self._deps.get_status_vm().items.subscribe(
                self._on_status_items
            )
        loop = self._deps.get_loop()
        if loop is not None:

            def _poll() -> None:
                observer.poll_into_queue()

            self._observe_poll_id = loop.add_interval(
                _OBSERVE_POLL_INTERVAL_S,
                _poll,
            )
            self._observe_drain_id = loop.add_interval(
                _OBSERVE_DRAIN_INTERVAL_S,
                self._coordinator.drain,
            )

    def stop(self) -> None:
        """Remove observe intervals and stop the backend."""
        self._worktree_watched = False
        self._last_worktree_dirty = None
        if self._observe_status_unsub is not None:
            self._observe_status_unsub()
            self._observe_status_unsub = None
        loop = self._deps.get_loop()
        if loop is not None:
            if self._observe_poll_id is not None:
                loop.remove_interval(self._observe_poll_id)
                self._observe_poll_id = None
            if self._observe_drain_id is not None:
                loop.remove_interval(self._observe_drain_id)
                self._observe_drain_id = None
        if self._observer is not None:
            self._observer.stop()
            self._observer = None
        self._coordinator = None

    def on_tab_switch(self) -> None:
        """Resync watch roots after TabView switches panels."""
        self.resync_roots()

    def set_preview_target(self, rel: str | None) -> None:
        """Update ObserveContext.preview_target for PREVIEW_FILE classification."""
        if self._observe_ctx is None:
            return
        self._observe_ctx = replace(self._observe_ctx, preview_target=rel)

    def build_roots(self) -> list[WatchRoot]:
        """Build watch roots; attach worktree only when Status is focused."""
        ctx = self._observe_ctx
        if ctx is None:
            return []
        roots: list[WatchRoot] = [
            WatchRoot(kind="git_dir", path=ctx.git_dir),
            WatchRoot(kind="common_dir", path=ctx.common_dir),
        ]
        self._worktree_watched = False
        if not self._deps.get_config().observe_worktree:
            return roots
        active = resolve_presentation_leaf(self._deps.get_tab_view().visible)
        if not isinstance(active, StatusPanel):
            return roots
        self._worktree_watched = True
        roots.append(WatchRoot(kind="worktree", path=ctx.repo_root))
        repo = Path(ctx.repo_root)
        for file_item in self._deps.get_status_vm().items.value:
            rel = file_item.get_file_str()
            if not rel or rel_path_is_denied(rel):
                continue
            roots.append(WatchRoot(kind="file", path=str(repo / rel)))
        return roots

    def resync_roots(self, *, reset: bool = False) -> None:
        """Start or update backend roots for the current tab / status files."""
        if self._observer is None or self._observe_ctx is None:
            return
        roots = self.build_roots()
        if reset:
            self._observer.start(roots)
        else:
            self._observer.update_roots(roots)

    def on_batch(self, batch: ChangeBatch) -> None:
        """Apply a debounced ChangeBatch to header and the active panel."""
        kinds = batch.kinds
        if (
            ChangeKind.HEAD in kinds
            or ChangeKind.REFS in kinds
            or ChangeKind.WORKTREE_META in kinds
            or ChangeKind.INDEX in kinds
            or ChangeKind.STASH in kinds
        ):
            # Branch tracking AND the worktree dirty dot both live in the
            # header; file edits (WORKTREE_META/INDEX) are the most common
            # dirty transition, so they must refresh it too.
            self._deps.schedule_reload_header()

        active = resolve_presentation_leaf(self._deps.get_tab_view().visible)
        if active is None:
            return

        if isinstance(active, StatusPanel):
            if ChangeKind.INDEX in kinds or ChangeKind.WORKTREE_META in kinds:
                self._deps.refresh_list_panel(active)
            if ChangeKind.PREVIEW_FILE in kinds:
                preview = self._deps.get_preview_panel()
                if (
                    self._deps.get_diff_preview_wanted()
                    and preview is not None
                    and self._deps.get_is_large_screen()
                ):
                    preview.reload()
            return

        if isinstance(active, BranchPanel):
            if ChangeKind.HEAD in kinds or ChangeKind.REFS in kinds:
                self._deps.refresh_list_panel(active)
                log_graph = self._deps.get_log_graph_preview()
                if (
                    self._deps.get_log_graph_wanted()
                    and log_graph is not None
                    and self._deps.get_is_large_screen()
                ):
                    log_graph.reload()
            return

        if isinstance(active, CommitPanel):
            if ChangeKind.HEAD in kinds or ChangeKind.REFS in kinds:
                self._deps.refresh_list_panel(active)
            return

        if isinstance(active, StashPanel):
            if ChangeKind.STASH in kinds or ChangeKind.REFS in kinds:
                self._deps.refresh_list_panel(active)

    def _worktree_digest(self) -> str | None:
        """Return a porcelain digest while Status worktree observe is active.

        Also records the raw dirty flag so the header can reuse this probe
        instead of running a second ``git status`` per refresh.
        """
        try:
            porcelain = self._deps.get_git().status_porcelain()
        except Exception:
            logging.debug("Worktree digest failed", exc_info=True)
            self._last_worktree_dirty = None
            return None
        self._last_worktree_dirty = bool(porcelain.strip())
        return hash_porcelain(porcelain)

    @property
    def worktree_dirty(self) -> bool | None:
        """Most recent worktree dirty flag while worktree observe is active.

        None when observe is inactive or a non-Status tab is focused, so
        callers fall back to a direct probe instead of a stale digest.
        """
        if not self._worktree_watched:
            return None
        return self._last_worktree_dirty

    def _on_status_items(self, _items: list) -> None:
        """Refresh worktree path set when the Status list changes."""
        self.resync_roots()

    def _context(self) -> ObserveContext:
        """Return the current ObserveContext (must be started)."""
        if self._observe_ctx is None:
            raise RuntimeError("ObserveContext not initialized")
        return self._observe_ctx
