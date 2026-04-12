# -*- coding:utf-8 -*-

"""Command methods.

This file encapsulates some methods corresponding to command.
All methods are must and only accept an `args` parameter -- a list or tuple
of parameters to be processed. If don't need will get a empty list or tuple.

Example:
>>> def func(args: Union[list, tuple]) -> str:
>>>     # your code.
>>>     pass
>>>     return "result msg."
"""

import re
from typing import Union

from pigit.ext.executor import WAITING
from pigit.ext.executor_factory import ExecutorFactory


def add(args: Union[list, tuple]) -> str:
    """git add option.

    Args:
        args (list): arguments list, maybe empty. need file string.
    """

    args_str = " ".join(args) if args else " ."
    ExecutorFactory.get().exec(f"git add {args_str}", flags=WAITING)

    return ":rainbow: Storage file: {0}".format(
        "all" if args_str.strip() == "." else args_str
    )


def fetch_remote_branch(args: Union[list, tuple]) -> str:
    "Fetch a remote branch to local and with the same name."

    branch = args[0] if args else None

    if branch:
        ExecutorFactory.get().exec(
            "git fetch origin {0}:{0} ".format(branch), flags=WAITING
        )
        return ""
    else:
        return "`This option need a branch name.`<error>"


def set_email_and_username(args: Union[list, tuple]) -> str:
    """Set git username and email with interaction.

    Args:
        args (list): arguments list, maybe empty.
    """

    print("Set the interactive environment of user name and email ...")

    is_global = next(
        (" --global " for i in args if i.strip() in ["-g", "--global"]), ""
    )

    print("Now set for global." if is_global else "Now set for local.")

    while True:
        name = input("Please input username:").strip()

        if name:
            break
        else:
            print("ERROR: Name is empty. continue ...")

    email_re = re.compile(r"^[0-9a-zA-Z_]{0,19}@[0-9a-zA-Z]{1,13}\.[com,cn,net]{1,3}$")
    while True:
        email = input("Please input email:")

        if email_re.match(email) is not None:
            break
        else:
            print("ERROR: Bad mailbox format. continue ...")

    executor = ExecutorFactory.get()
    if executor.exec(
        f"git config user.name {name} {is_global}", flags=WAITING
    ) and executor.exec(f"git config user.email {email} {is_global}", flags=WAITING):
        print("Successfully set.")
    else:
        print("Failed. Please check log.")

    return ""
