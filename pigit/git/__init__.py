from __future__ import annotations

from pigit.ext.executor import REPLY, DECODE
from pigit.ext.executor_factory import get_executor

from .ignore import get_ignore_source, create_gitignore
from .api import GitApi, GitError, RepoError
from .managed_repos import ManagedRepos

__all__ = (
    "git_version",
    "get_ignore_source",
    "create_gitignore",
    "GitApi",
    "GitError",
    "RepoError",
    "ManagedRepos",
)


def git_version() -> str:
    """Get Git version."""

    _, _, version = get_executor().exec("git --version", flags=REPLY | DECODE)
    if version is None:
        return ""
    if isinstance(version, bytes):
        return version.decode().strip() or ""
    return version.strip() or ""
