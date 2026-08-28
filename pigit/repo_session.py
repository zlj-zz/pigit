"""
Module: pigit/repo_session.py
Description: Rebuildable repository session holding GitApi and panel ViewModels.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .git.api import GitApi
from .viewmodels.branch import BranchViewModel
from .viewmodels.commit import CommitViewModel
from .viewmodels.status import StatusViewModel
from .session_history import SessionHistory


@dataclass
class RepoSession:
    """One repository's git binding and list ViewModels for the TUI.

    Built by :meth:`build`; disposed by :meth:`dispose` when the session is
    replaced or the application exits (later phases). Phase 1 only extracts
    construction so the session is a rebuildable unit.
    """

    git: GitApi
    repo_path: str
    repo_name: str
    status_vm: StatusViewModel
    commit_vm: CommitViewModel
    branch_vm: BranchViewModel

    @staticmethod
    def build(
        git_api: GitApi,
        path: str | None,
        history: SessionHistory,
    ) -> RepoSession:
        """Confirm ``path`` (or cwd), bind git, and construct the three VMs.

        Args:
            git_api: Unbound (or previously bound) GitApi factory.
            path: Path to confirm; ``None`` uses the same discovery as
                ``GitApi.confirm_repo()`` with no argument.
            history: Shared session undo stack passed to Status/Branch VMs.

        Returns:
            A session whose ``repo_path`` is the resolved work-tree root.
        """
        repo_path, _conf = git_api.confirm_repo(path)
        git = git_api.bind_path(repo_path)
        repo_name = os.path.basename(repo_path) if repo_path else ""
        return RepoSession(
            git=git,
            repo_path=repo_path,
            repo_name=repo_name,
            status_vm=StatusViewModel(git, history=history),
            commit_vm=CommitViewModel(git),
            branch_vm=BranchViewModel(git, history=history),
        )

    def dispose(self) -> None:
        """Cancel pending VM loads and clear ViewModel signal subscriptions."""
        for vm in (self.status_vm, self.commit_vm, self.branch_vm):
            vm.dispose()
