from pigit.ext.executor import REPLY, DECODE
from pigit.ext.executor_factory import ExecutorFactory

from .ignore import get_ignore_source, create_gitignore
from .cmd_builtin import builtin_cmds
from .cmd_proxy import get_extra_cmds, GitProxy, GitCommandType
from .repo import LocalGit, ManagedRepos, Repo

__all__ = (
    "git_version",
    "get_ignore_source",
    "create_gitignore",
    "get_extra_cmds",
    "GitProxy",
    "GitCommandType",
    "builtin_cmds",
    "LocalGit",
    "ManagedRepos",
    "Repo",
)


# _Executor: Optional[Executor] = None


# def _get_executor() -> Executor:
#     global _Executor
#     if _Executor is None:
#         _Executor = Executor()

#     return _Executor


def git_version() -> str:
    """Get Git version."""

    _, _, _version = ExecutorFactory.get().exec("git --version", flags=REPLY | DECODE)
    return _version.strip() or ""
