# -*- coding:utf-8 -*-

"""Command methods.

This file encapsulates some methods corresponding to command.
All methods are must and only accept an `args` parameter -- a list
of parameters to be processed.
"""

import re

from ..utils import run_cmd, color_print
from ..common import Emotion, TermColor


def add(args):
    args_str = " ."
    if args:
        args_str = " ".join(args)

    print(
        "{} Storage file: {}".format(
            Emotion.Icon_Rainbow, "all" if args_str.strip() == "." else args_str
        )
    )
    run_cmd("git add " + args_str)


def fetch_remote_branch(args):
    branch = args[0] if len(args) > 1 else None

    if branch:
        run_cmd("git fetch origin {}:{} ".format(branch, branch))
    else:
        color_print("This option need a branch name.", TermColor.Red)


def set_email_and_username(args):
    print("Set the interactive environment of user name and email ...")
    __global = re.compile(r"\-\-global")
    for i in args:
        r = __global.search(i)
        if r is not None:
            other = " --global "
            print("Now set for global.")
            break
    else:
        print("Now set for local.")
        other = " "

    name = input("Please input username:")
    while True:
        if not name:
            color_print("Name is empty.", TermColor.Red)
            name = input("Please input username again:")
        else:
            break

    email = input("Please input email:")
    email_re = re.compile(r"^[0-9a-zA-Z_]{0,19}@[0-9a-zA-Z]{1,13}\.[com,cn,net]{1,3}$")
    while True:
        if email_re.match(email) is None:
            color_print("Bad mailbox format.", TermColor.Red)
            email = input("Please input email again:")
        else:
            break

    if run_cmd("git config user.name" + other + name) and run_cmd(
        "git config user.email" + other + email
    ):
        color_print("Successfully set.", TermColor.Green)
    else:
        color_print("Failed. Please check log.", TermColor.Red)
