# -*- coding:utf-8 -*-

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from plenty import get_console

if TYPE_CHECKING:
    from ..config import Config
    from ..context import Context
    from ..git.local_git import LocalGit
    from ..git.managed_repos import ManagedRepos


class BaseHandler(ABC):
    """Base for top-level interaction modes (TUI, cmd, etc.)."""

    def __init__(self, ctx: "Context") -> None:
        self.ctx = ctx
        self.console = get_console()

    @property
    def config(self) -> "Config":
        return self.ctx.config

    @property
    def local_git(self) -> "LocalGit":
        return self.ctx.local_git

    @property
    def managed_repos(self) -> "ManagedRepos":
        return self.ctx.managed_repos

    def preprocess(self) -> bool:
        """Return False to skip ``execute`` (e.g. unsupported platform)."""
        return True

    @abstractmethod
    def execute(self) -> None:
        """Run the mode."""
