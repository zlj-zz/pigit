"""
Module: pigit/viewmodels/commit.py
Description: CommitPanel ViewModel.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
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
class _CommitBatch:
    """One streamed slice of the commit log, applied on the UI thread."""

    commits: list[Commit]
    requested: str
    resolved: str
    graph_rows: list[GraphRow]
    remotes: tuple[str, ...]
    # True for a stream's first batch, which replaces whatever the previous
    # stream left on screen; later batches extend the list.
    first: bool


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

    def get_commit_bodies(self, shas: Sequence[str]) -> dict[str, str]: ...


class CommitViewModel(ViewModelBase["Commit"], ICommitViewModel):
    """Concrete ViewModel for commit log."""

    # Commits per streamed batch: the first one paints, the rest follow.
    STREAM_BATCH = 500

    def __init__(self, git: GitApi, log_limit: int | None = None) -> None:
        """Wire the view model.

        Args:
            git: Git facade bound to the repository.
            log_limit: Max commits to read from ``git log``; ``None`` or ``0``
                means no limit. The caller supplies this from app config so the
                view-model layer stays free of a config dependency.
        """
        super().__init__()
        self._git = git
        self._log_limit = log_limit
        head = git.get_head() or "HEAD"
        self._head: str = head
        self._log_ref: str = head
        self._graph_rows: Signal[list[GraphRow]] = Signal([])
        self._remotes: Signal[tuple[str, ...]] = Signal(())

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
        """Start a background stream; batches are applied on the UI thread."""
        self._loader.start_stream(
            self._stream_commits, self._guarded(self._apply_batch)
        )

    def _iter(self, ref: str) -> Iterator[Commit]:
        """Read ``ref`` as a generator, honouring the configured limit."""
        if self._log_limit and self._log_limit > 0:
            return self._git.iter_commits(ref, max_commits=self._log_limit)
        return self._git.iter_commits(ref, limit=False)

    def _stream_commits(self, emit: Callable[[_CommitBatch], bool]) -> None:
        """Worker: read the log in batches and emit each one.

        The history is read once; a pinned ref that yields nothing is verified
        and retried against the checkout, so the common auto-refresh path never
        pays for a rev-parse.
        """
        requested = self._log_ref
        remotes = tuple(self._git.get_remotes())
        if self._stream_ref(emit, requested, requested, remotes):
            return
        if self.viewing_checkout_log():
            return
        try:
            self._git.verify_commitish(requested)
        except GitError:
            self._stream_ref(emit, requested, self._head, remotes)

    def _stream_ref(
        self,
        emit: Callable[[_CommitBatch], bool],
        requested: str,
        ref: str,
        remotes: tuple[str, ...],
    ) -> bool:
        """Emit ``ref`` in batches; True once any batch was delivered.

        Stops pulling the moment ``emit`` reports the stream is superseded:
        abandoning the generator closes the git pipe instead of walking the
        rest of the history in the background.
        """
        from pigit.app_log_graph import GraphLayout

        layout = GraphLayout()
        pending: list[Commit] = []
        first = True
        delivered = False
        for commit in self._iter(ref):
            pending.append(commit)
            if len(pending) < self.STREAM_BATCH:
                continue
            if not self._emit_batch(
                emit, pending, layout, requested, ref, remotes, first
            ):
                return True
            delivered, first, pending = True, False, []
        if pending:
            self._emit_batch(emit, pending, layout, requested, ref, remotes, first)
            delivered = True
        return delivered

    @staticmethod
    def _emit_batch(
        emit: Callable[[_CommitBatch], bool],
        commits: list[Commit],
        layout,
        requested: str,
        ref: str,
        remotes: tuple[str, ...],
        first: bool,
    ) -> bool:
        """Hand one batch (with its own graph rows) to the emitter."""
        return emit(
            _CommitBatch(
                commits=commits,
                requested=requested,
                resolved=ref,
                graph_rows=layout.extend(commits),
                remotes=remotes,
                first=first,
            )
        )

    def _apply_batch(self, batch: _CommitBatch) -> None:
        """Apply one batch on the UI thread, unless superseded.

        The stream's first batch replaces the list (a refresh must not append
        onto the previous stream's rows); later batches extend it. Derived
        ``graph_rows`` / ``remotes`` are published before ``items`` so list
        subscribers rebuild row caches with rails ready.
        """
        if batch.requested != self._log_ref:
            return
        self._log_ref = batch.resolved
        if batch.first:
            self._graph_rows.set(batch.graph_rows)
            self._remotes.set(batch.remotes)
            super()._on_loaded(batch.commits)
            return
        self._graph_rows.set(self._graph_rows.value + batch.graph_rows)
        self._items.set(self._items.value + batch.commits)

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
            author_email=c.author_email,
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

    def get_commit_bodies(self, shas: Sequence[str]) -> dict[str, str]:
        """Return ``{sha: full body}`` for exactly the requested commits."""
        return self._git.get_commit_bodies(list(shas))
