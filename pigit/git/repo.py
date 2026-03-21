# -*- coding:utf-8 -*-

from pathlib import Path
from typing import Callable, Optional, Union

from pigit.ext.executor_factory import ExecutorFactory

from .local_git import LocalGit, RepoError
from .managed_repos import ManagedRepos
from .model import File

GitFileT = Union[File, str]
GitFuncT = Callable[[GitFileT], None]


class Repo(LocalGit, ManagedRepos):
    """Git helpers: single-repo commands (`LocalGit`) + multi-repo registry (`ManagedRepos`)."""

    def __init__(
        self, path: Optional[str] = None, repo_json_path: Optional[str] = None
    ) -> None:
        executor = ExecutorFactory.get()
        LocalGit.__init__(self, executor, path)
        ManagedRepos.__init__(self, executor, repo_json_path)

    def update_setting(
        self, *, op_path: Optional[str] = None, repo_info_path: Optional[str] = None
    ) -> "Repo":
        if op_path is not None:
            self.path = op_path
        if repo_info_path is not None:
            self.repo_json_path = Path(repo_info_path)
        return self

    def bind_path(self, path: str) -> LocalGit:
        """Pin a repo root while sharing `executor` (e.g. TUI panels after `confirm_repo`)."""
        return LocalGit(self.executor, path)
