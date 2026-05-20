# -*- coding: utf-8 -*-
"""
Module: pigit/cmdparse/completion/__init__.py
Description: Shell completion script generation dispatcher.
Author: Zev
Date: 2026-05-20
"""

from __future__ import annotations

from .base import ShellCompletion
from .bash import BashCompletion
from .zsh import ZshCompletion
from .fish import FishCompletion

__all__ = [
    "ShellCompletion",
    "BashCompletion",
    "ZshCompletion",
    "FishCompletion",
    "shell_complete",
]

_Supported_Shell: dict[str, type[ShellCompletion]] = {
    "bash": BashCompletion,
    "zsh": ZshCompletion,
    "fish": FishCompletion,
}


def shell_complete(
    complete_vars: dict,
    shell: str | None = None,
    prog: str | None = None,
    script_dir: str | None = None,
    script_name: str | None = None,
) -> str:
    """Generate completion script source and return it.

    Args:
        complete_vars (Dict): a dict of ~Parser serialization.
        shell (Optional[str], optional): shell name. Defaults to None.
        prog (Optional[str], optional): cmd prog. Defaults to None.
        script_dir (Optional[str], optional): where the script saved. Defaults to None.
        script_name (Optional[str], optional): completion script name. Defaults to None.

    Returns:
        Completion script source string, or empty string on unsupported shell.
    """
    if not shell:
        return ""

    shell = shell.lower().strip()
    if shell not in _Supported_Shell:
        return ""

    complete_handle = _Supported_Shell[shell](
        prog, complete_vars, script_dir, script_name
    )
    return complete_handle.generate_resource()
