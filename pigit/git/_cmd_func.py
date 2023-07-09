# -*- coding:utf-8 -*-

"""Command methods.

This file encapsulates some methods corresponding to command.
All methods are must and only accept an `args` parameter -- a list or tuple
of parameters to be processed. If don't need will get a empty list or tuple.

Like this:
>>> def func(args: Union[list, tuple]) -> None:
>>>     # your code.
>>>     pass
"""

from typing import List, Tuple, Union

from plenty import echo

from ..common.utils import exec_cmd


def add(args: Union[List, Tuple]) -> None:
    """git add option.

    Args:
        args (list): arguments list, maybe empty. need file string.
    """

    args_str = " ".join(args) if args else " ."
    echo(
        ":rainbow: Storage file: {0}".format(
            "all" if args_str.strip() == "." else args_str
        )
    )
    exec_cmd(f"git add {args_str}", reply=False)


def fetch_remote_branch(args: Union[List, Tuple]) -> None:
    "Fetch a remote branch to local and with the same name."

    branch = args[0] if len(args) > 1 else None

    if branch:
        exec_cmd("git fetch origin {0}:{0} ".format(branch), reply=False)
    else:
        echo("`This option need a branch name.`<error>")


def set_email_and_username(args: Union[List, Tuple]) -> None:
    """Set git username and email with interaction.

    Args:
        args (list): arguments list, maybe empty.
    """

    print("Set the interactive environment of user name and email ...")

    is_global = next(
        (" --global " for i in args if i.strip() in ["-g", "--global"]), ""
    )

    if is_global:
        print("Now set for global.")
    else:
        print("Now set for local.")

    while True:
        name = input("Please input username:").strip()

        if name:
            break
        else:
            echo("`Name is empty.`<error>")

    import re

    email_re = re.compile(r"^[0-9a-zA-Z_]{0,19}@[0-9a-zA-Z]{1,13}\.[com,cn,net]{1,3}$")
    while True:
        email = input("Please input email:")

        if email_re.match(email) is not None:
            break
        else:
            echo("`Bad mailbox format.`<error>")

    if exec_cmd(f"git config user.name {name} {is_global}", reply=False) and exec_cmd(
        f"git config user.email {email} {is_global}", reply=False
    ):
        echo("`Successfully set.`<ok>")
    else:
        echo("`Failed. Please check log.`<error>")
