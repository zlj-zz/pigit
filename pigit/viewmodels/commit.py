"""
Module: pigit/viewmodels/commit.py
Description: CommitPanel ViewModel.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pigit.termui.reactive import Signal

from .base import ActionResult, IListViewModel, ViewModelBase

if TYPE_CHECKING:
    from pigit.app_types import CommitInfo, GraphRow
    from pigit.git.local_git import LocalGit
    from pigit.git.model import Commit


class ICommitViewModel(IListViewModel["Commit"]):
    """Protocol for CommitPanel's ViewModel."""

    @property
    def repo_path(self) -> str: ...
    @property
    def graph_rows(self) -> list[GraphRow]: ...
    @property
    def remotes(self) -> tuple[str, ...]: ...
    def get_inspector_data(self, idx: int) -> CommitInfo | None: ...
    def load_diff(self, idx: int) -> list[str]: ...
    def get_bodies(self) -> dict[str, str] | None: ...


class CommitViewModel(ViewModelBase["Commit"], ICommitViewModel):
    """Concrete ViewModel for commit log."""

    def __init__(self, git: LocalGit) -> None:
        super().__init__()
        self._git = git
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

    def _do_load(self) -> list[Commit]:
        branch_name = self._git.get_head() or ""
        commits = self._git.load_commits(branch_name)
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
        branch_name = self._git.get_head() or ""
        self._bodies = self._git.get_commit_bodies(branch_name)
        return self._bodies
