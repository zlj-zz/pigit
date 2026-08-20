"""
Module: pigit/viewmodels/commit.py
Description: CommitPanel ViewModel.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pigit.termui.reactive import Signal
from pigit.git.api import GitError

from .base import IListViewModel, ViewModelBase

if TYPE_CHECKING:
    from pigit.app_types import CommitSnapshot, GraphRow
    from pigit.git.api import GitApi
    from pigit.git.model import Commit


@dataclass
class _CommitLoad:
    """Result of a background commit-log load, applied on the UI thread."""

    commits: list[Commit]
    requested: str
    resolved: str
    graph_rows: list[GraphRow]
    remotes: tuple[str, ...]


class ICommitViewModel(IListViewModel["Commit"]):
    """Protocol for CommitPanel's ViewModel."""

    @property
    def repo_path(self) -> str: ...

    @property
    def graph_rows(self) -> list[GraphRow]: ...

    @property
    def remotes(self) -> tuple[str, ...]: ...

    @property
    def log_ref(self) -> str: ...

    def set_log_ref(self, ref: str) -> None: ...

    def follow_head(self, ref: str) -> bool: ...

    def viewing_checkout_log(self) -> bool: ...

    def list_log_ref_names(self) -> list[str]: ...

    def get_inspector_snapshot(self, idx: int) -> CommitSnapshot | None: ...

    def load_diff(self, idx: int) -> list[str]: ...

    def get_bodies(self) -> dict[str, str] | None: ...


class CommitViewModel(ViewModelBase["Commit"], ICommitViewModel):
    """Concrete ViewModel for commit log."""

    def __init__(self, git: GitApi) -> None:
        super().__init__()
        self._git = git
        head = git.get_head() or "HEAD"
        self._head: str = head
        self._log_ref: str = head
        self._graph_rows: Signal[list[GraphRow]] = Signal([])
        self._remotes: Signal[tuple[str, ...]] = Signal(())
        self._bodies: dict[str, str] | None = None

    @property
    def repo_path(self) -> str:
        return self._git.path or ""

    @property
    def graph_rows(self) -> list[GraphRow]:
        return self._graph_rows.value

    @property
    def remotes(self) -> tuple[str, ...]:
        return self._remotes.value

    @property
    def log_ref(self) -> str:
        return self._log_ref

    def set_log_ref(self, ref: str) -> None:
        """Pin the commit list to ``ref`` (validated asynchronously on load)."""
        ref = ref.strip()
        if not ref:
            return
        self._log_ref = ref
        self._bodies = None
        self.refresh()

    def follow_head(self, ref: str) -> bool:
        """Point the list at the current checkout; True when it overrode a pin.

        Called after every HEAD-moving operation (checkout, create, rename,
        undo) so ``_log_ref`` never goes stale.
        """
        was_pinned = self._log_ref not in ("HEAD", self._head)
        self._head = ref
        self.set_log_ref(ref)
        return was_pinned

    def viewing_checkout_log(self) -> bool:
        """True when the list is the current checkout (no subprocess)."""
        return self._log_ref == "HEAD" or self._log_ref == self._head

    def list_log_ref_names(self) -> list[str]:
        """Return ``HEAD`` plus ``load_branches(scope='all')`` short names."""
        names = ["HEAD"]
        for branch in self._git.load_branches(scope="all"):
            if branch.name != "HEAD":
                names.append(branch.name)
        return names

    def refresh(self) -> None:
        """Start a background load; the result is applied on the UI thread."""
        self._loader.start(self._load_commits, self._apply_load)

    def _load_commits(self) -> _CommitLoad:
        requested = self._log_ref
        ref = requested
        commits = self._git.load_commits(ref)
        if not commits and not self.viewing_checkout_log():
            # An empty pinned log is either an unborn/empty branch or a
            # dangling ref (deleted/renamed). Verify only then, so the
            # common auto-refresh path (ref unchanged, commits present)
            # never pays for an extra rev-parse.
            try:
                self._git.verify_commitish(ref)
            except GitError:
                ref = self._head
                commits = self._git.load_commits(ref)
        remotes = tuple(self._git.get_remotes())
        from pigit.app_commit_graph import compute_graph_rows

        graph_rows = compute_graph_rows(commits) if commits else []
        return _CommitLoad(
            commits=commits,
            requested=requested,
            resolved=ref,
            graph_rows=graph_rows,
            remotes=remotes,
        )

    def _apply_load(self, result: _CommitLoad) -> None:
        """Apply a load result on the UI thread, unless superseded.

        ``_load_commits`` runs on the AsyncTask worker; it never writes shared
        state. Derived ``graph_rows`` / ``remotes`` must be published before
        ``items`` so list subscribers rebuild row caches with rails ready.
        """
        if result.requested != self._log_ref:
            return
        self._log_ref = result.resolved
        self._graph_rows.set(result.graph_rows)
        self._remotes.set(result.remotes)
        self._bodies = None
        super()._on_loaded(result.commits)

    def get_inspector_snapshot(self, idx: int):
        c = self.item_at(idx)
        if c is None:
            return None
        return self._memo_inspector(
            ("commit", c.sha), lambda: self._build_commit_snapshot(c)
        )

    def _build_commit_snapshot(self, c: Commit):
        from pigit.app_types import CommitSnapshot
        from pigit.ext.utils import relative_time

        files, total_add, total_del = self._git.get_commit_stats(c.sha)
        return CommitSnapshot(
            identity=c.sha[:7],
            sha=c.sha,
            msg=c.msg,
            author=c.author,
            when=relative_time(c.unix_timestamp),
            status=c.status,
            tags=", ".join(c.tag) if c.tag else "none",
            parents=list(c.parents),
            files=files,
            total_add=total_add,
            total_del=total_del,
        )

    def load_diff(self, idx: int) -> list[str]:
        c = self.item_at(idx)
        if c is None:
            return []
        text = self._git.load_commit_info(c.sha, plain=True)
        return text.splitlines()

    def get_bodies(self) -> dict[str, str] | None:
        if self._bodies is not None:
            return self._bodies
        if not self._items.value:
            return None
        self._bodies = self._git.get_commit_bodies(self._log_ref)
        return self._bodies
