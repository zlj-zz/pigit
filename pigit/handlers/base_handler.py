# -*- coding:utf-8 -*-

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from plenty import get_console

if TYPE_CHECKING:
    from ..config import Config
    from ..context import Context
    from ..git.repo import Repo


class BaseHandler(ABC):
    """Base for top-level interaction modes (TUI, cmd, etc.)."""

    def __init__(self, ctx: "Context") -> None:
        self.ctx = ctx
        self.console = get_console()

    @property
    def config(self) -> "Config":
        return self.ctx.config

    @property
    def repo(self) -> "Repo":
        return self.ctx.repo

    def preprocess(self) -> bool:
        """Return False to skip ``execute`` (e.g. unsupported platform)."""
        return True

    @abstractmethod
    def execute(self) -> None:
        """Run the mode."""
