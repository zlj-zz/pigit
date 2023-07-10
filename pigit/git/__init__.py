from pigit.common.utils import exec_cmd

from .ignore import get_ignore_source, create_gitignore
from .cmd import SCmd, similar_command
from .repo import Repo


def git_version() -> str:
    """Get Git version."""

    _, _version = exec_cmd("git --version")
    return _version.strip() or ""
