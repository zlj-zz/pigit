"""
Module: pigit/viewmodels/commit.py
Description: CommitPanel ViewModel.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pigit.termui.reactive import Signal
from pigit.git.api import GitError

from .base import IListViewModel, ViewModelBase

if TYPE_CHECKING:
    from pigit.app_types import CommitInfo, GraphRow
    from pigit.git.api import GitApi
    from pigit.git.model import Commit


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

    def get_inspector_data(self, idx: int) -> CommitInfo | None: ...

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

    def _do_load(self) -> list[Commit]:
        try:
            self._git.verify_commitish(self._log_ref)
        except GitError:
            # The pinned ref dangled (deleted/renamed); fall back to the
            # current checkout so the list and title stay correct.
            self._log_ref = self._head
        commits = self._git.load_commits(self._log_ref)
        remotes = tuple(self._git.get_remotes())
        from pigit.app_commit_graph import compute_graph_rows

        graph_rows = compute_graph_rows(commits) if commits else []
        self._graph_rows.set(graph_rows)
        self._remotes.set(remotes)
        self._bodies = None
        return commits

    def get_inspector_data(self, idx: int) -> CommitInfo | None:
        c = self.item_at(idx)
        if c is None:
            return None
        changed_files, total_add, total_del = self._git.get_commit_stats(c.sha)
        from pigit.app_types import CommitInfo

        return CommitInfo(
            commit=c,
            changed_files=changed_files,
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
