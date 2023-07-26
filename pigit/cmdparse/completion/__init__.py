# -*- coding:utf-8 -*-

from typing import Dict, Optional, Type

from .base import ShellCompletion
from .bash import BashCompletion
from .zsh import ZshCompletion
from .fish import FishCompletion


_Supported_Shell: Dict[str, Type[ShellCompletion]] = {
    "bash": BashCompletion,
    "zsh": ZshCompletion,
    "fish": FishCompletion,
}


def shell_complete(
    complete_vars: Dict,
    shell: Optional[str] = None,
    prog: Optional[str] = None,
    script_dir: Optional[str] = None,
    script_name: Optional[str] = None,
) -> None:
    """Generate completion script source and print.

    Args:
        complete_vars (Dict): a dict of ~Parser serialization.
        shell (Optional[str], optional): shell name. Defaults to None.
        prog (Optional[str], optional): cmd prog. Defaults to None.
        script_dir (Optional[str], optional): where the script saved. Defaults to None.
        script_name (Optional[str], optional): completion script name. Defaults to None.
    """

    # check shell effectiveness
    shell = (
        get_shell()
        if shell is None or shell not in _Supported_Shell
        else shell.lower().strip()
    )

    if not shell:
        # No shell be found!
        print("")
        return

    if shell not in _Supported_Shell:
        # not support shell
        print("")
        return

    complete_handle = _Supported_Shell[shell](
        prog, complete_vars, script_dir, script_name
    )

    # try create completion file.
    completion_src = complete_handle.generate_resource()
    print(completion_src)


def get_shell() -> str:
    """Gets the currently used shell.

    Returns:
        (str): Current shell string.
    """
    import os

    try:
        shell_string = os.environ["SHELL"]
        return shell_string.split("/")[-1].strip()
    except KeyError:
        return ""
