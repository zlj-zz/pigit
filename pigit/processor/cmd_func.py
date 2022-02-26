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

import re
from typing import Union

from ..common import Emoji, exec_cmd, run_cmd, render_str


def add(args: Union[list, tuple]) -> None:
    """git add option.

    Args:
        args (list): arguments list, maybe empty. need file string.
    """

    # default add all.
    args_str = " ."
    # process arguments if has.
    if args:
        args_str = " ".join(args)

    print(
        "{0} Storage file: {1}".format(
            Emoji.rainbow, "all" if args_str.strip() == "." else args_str
        )
    )
    run_cmd("git add " + args_str)


def fetch_remote_branch(args: Union[list, tuple]) -> None:
    "Fetch a remote branch to local and with the same name."

    branch = args[0] if len(args) > 1 else None

    if branch:
        run_cmd("git fetch origin {0}:{0} ".format(branch))
    else:
        print(render_str("`This option need a branch name.`<error>"))


def set_email_and_username(args: Union[list, tuple]) -> None:
    """Set git username and email with interaction.

    Args:
        args (list): arguments list, maybe empty.
    """

    print("Set the interactive environment of user name and email ...")

    is_global = ""
    _global = re.compile(r"\-\-global")

    for i in args:
        r = _global.search(i)
        if r is not None:
            is_global = " --global "
            break

    if is_global:
        print("Now set for global.")
    else:
        print("Now set for local.")

    name = input("Please input username:").strip()
    while True:
        if not name:
            print(render_str("`Name is empty.`<error>"))
            name = input("Please input username again:")
        else:
            break

    email = input("Please input email:")
    email_re = re.compile(r"^[0-9a-zA-Z_]{0,19}@[0-9a-zA-Z]{1,13}\.[com,cn,net]{1,3}$")
    while True:
        if email_re.match(email) is None:
            print(render_str("`Bad mailbox format.`<error>"))
            email = input("Please input email again:")
        else:
            break

    if run_cmd(f"git config user.name {name} {is_global}") and run_cmd(
        f"git config user.email {email} {is_global}"
    ):
        print(render_str("`Successfully set.`<ok>"))
    else:
        print(render_str("`Failed. Please check log.`<error>"))
