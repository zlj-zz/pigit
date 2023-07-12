from pigit.common.utils import exec_cmd

from .ignore import get_ignore_source, create_gitignore
from .cmd import get_extra_cmds, SCmd, CommandType, GIT_CMDS
from .repo import Repo

__all__ = (
    "get_version",
    "get_ignore_source",
    "create_gitignore",
    "get_extra_cmds",
    "SCmd",
    "CommandType",
    "GIT_CMDS",
    "Repo",
)


def git_version() -> str:
    """Get Git version."""

    _, _version = exec_cmd("git --version")
    return _version.strip() or ""
