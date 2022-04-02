# -*- coding:utf-8 -*-

from typing import Dict, Optional

from .bash import BashCompletion
from .zsh import ZshCompletion
from .fish import FishCompletion


supported_shell = {
    "bash": BashCompletion,
    "zsh": ZshCompletion,
    "fish": FishCompletion,
}


def shell_complete(
    complete_vars: Dict,
    script_dir: Optional[str] = None,
    shell: Optional[str] = None,
    prog: Optional[str] = None,
    script_name: Optional[str] = None,
    inject_path: Optional[str] = None,
    inject: bool = True,
) -> None:
    """Generate completion script source and try to injecting.

    Args:
        complete_vars (Dict): a dict of ~Parser serialization.
        script_dir (Optional[str], optional): where the script saved. Defaults to None.
        shell (Optional[str], optional): shell name. Defaults to None.
        prog (Optional[str], optional): cmd prog. Defaults to None.
        script_name (Optional[str], optional): completion script name. Defaults to None.
        inject_path (Optional[str], optional): where the script injecting. Defaults to None.
        inject (bool, optional): whether inject script. Defaults to True.
    """

    # check shell validable.
    shell = get_shell() if shell is None else shell.lower().strip()
    if not shell:
        print("No shell be found!")
        return

    if shell not in supported_shell:
        print(
            "shell name '{0}' is not supported, see {1}".format(
                shell, supported_shell.keys()
            )
        )
        return

    print("\n===Try to add completion ...")
    print(f":: Completion shell: {repr(shell)}")

    complete_handle = supported_shell[shell](
        prog, complete_vars, script_dir, script_name, inject_path
    )

    # try create completion file.
    completion_src = complete_handle.generate_resource()
    if not inject or not script_dir:
        print(completion_src)
        return

    if not complete_handle.write_completion(completion_src):
        print(":: Write completion script failed!")
        return None
    else:
        print(":: Write completion script success.")

    # try inject to shell config.
    try:
        injected = complete_handle.inject_into_shell()
        if injected:
            print(":: Source your shell configuration.")
        else:
            print(":: Command already exist.")
    except Exception as e:
        print(e)


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
