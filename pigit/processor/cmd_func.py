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


def open_remote_url(args: Union[list, tuple]) -> None:
    """Open remote.

    Open the remote repository through the browser. Support additional parameter list.
    When multiple parameters exist at the same time, only one will take effect.

    -i, --issue:
        open given issue of the repository.
        pigit open -- -i 20
        pigit open -- --issue=20
    -c, --commit:
        open the current commit in the repo website.
        pigit open -- --commit
    -p, --print:
        only print the url at the terminal, but don't open it.
    <branch>:
        open the page for this branch on the repo website.
    """

    err, branches = exec_cmd("git branch")

    branch = issue = commit = ""
    if args:
        i = 0
        while i < len(args):
            # -i 29 or --issue 29
            if args[i].strip() in ["-i", "--issue"]:
                try:
                    issue_number = args[i + 1]
                    int(issue_number)
                    issue = "/issues/{0}".format(issue_number)
                    i += 2
                except:
                    i += 1

            # -i=29 or --issue=29
            elif ("-i" in args[i] or "--issue" in args[i]) and "=" in args[i]:
                issue_number = args[i].split("=")[-1]
                try:
                    int(issue_number)
                    issue = "/issues/{0}".format(issue_number)
                finally:
                    i += 1
            elif args[i].strip() in ["-c", "--commit"]:
                err, commit_hash = exec_cmd("git log -n1 --format=format:'%H'")
                if len(commit_hash.strip()) == 40:
                    commit = "/commit/{0}".format(commit_hash.strip())
                i += 1
            else:
                if re.search(args[i], branches):
                    branch = "/tree/{0}".format(args[i])
                i += 1

    # Get remote name, exit when error.
    err, remote = exec_cmd("git remote show")
    if err:
        print(err)
        return None
    remote = remote.strip().split("\n")[0]

    # Get remote url, exit when error.
    err, remote_url = exec_cmd("git ls-remote --get-url {0}".format(remote))
    if err:
        print(err)
        return None
    remote_url = remote_url[:-5]

    # Splice URL, priority: branch > commit > issue
    if branch:
        remote_url += branch
    elif commit:
        remote_url += commit
    elif issue:
        remote_url += issue

    # Adjust whether just need print.
    if "-p" in args or "--print" in args:
        print(remote_url)
    else:
        import webbrowser

        webbrowser.open(remote_url + branch)
