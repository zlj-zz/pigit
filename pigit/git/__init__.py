from pigit.ext.executor import REPLY, DECODE
from pigit.ext.executor_factory import ExecutorFactory

from .ignore import get_ignore_source, create_gitignore
from .repo import LocalGit, ManagedRepos, Repo

__all__ = (
    "git_version",
    "get_ignore_source",
    "create_gitignore",
    "LocalGit",
    "ManagedRepos",
    "Repo",
)


def git_version() -> str:
    """Get Git version."""

    _, _, _version = ExecutorFactory.get().exec("git --version", flags=REPLY | DECODE)
    return _version.strip() or ""
