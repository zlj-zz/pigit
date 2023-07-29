from pigit.comm.executor import Executor, REPLY, DECODE

from .ignore import get_ignore_source, create_gitignore
from .cmd import get_extra_cmds, SCmd, CommandType, GIT_CMDS
from .repo import Repo

__all__ = (
    "git_version",
    "get_ignore_source",
    "create_gitignore",
    "get_extra_cmds",
    "SCmd",
    "CommandType",
    "GIT_CMDS",
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

    _, _, _version = Executor().exec("git --version", flags=REPLY | DECODE)
    return _version.strip() or ""
