# -*- coding:utf-8 -*-

from __future__ import print_function
import re
import random

from ..utils import run_cmd, color_print, confirm, similar_command
from ..str_utils import shorten
from ..common import Emotion, Color, TermColor, Fx
from ..git_utils import Git_Version
from .interaction import InteractiveAdd, TermError


class GitOptionSign:
    """Storage command type."""

    # command type.
    String = 1
    Func = 1 << 2
    # Accept parameters.
    No = 1 << 3
    Multi = 1 << 4


class GitProcessor(object):
    """Git short command processor.

    Subclass: _Function

    Attributes:
        Types (list): The short command type list.
        Git_Options (dict): Available short commands dictionaries.
            >>> d = {
            ...     'short_command': {
            ...         'state': GitOptionState.String,
            ...         'command': 'git status --short',
            ...         'help_msg': 'display repository status.'
            ...     }
            ... }
            >>> print(d)
    """

    Types = [
        "Branch",
        "Commit",
        "Conflict",
        "Fetch",
        "Index",
        "Log",
        "Merge",
        "Push",
        "Remote",
        "Stash",
        "Tag",
        "Working tree",
        "Setting",
    ]

    class _Function(object):
        """Command methods class.

        This class encapsulates some methods corresponding to command.
        All methods are [classmethod] or [staticmethod], must and only
        accept an `args` parameter -- a list of parameters to be processed.
        """

        @staticmethod
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

        @staticmethod
        def fetch_remote_branch(args):
            branch = args[0] if len(args) > 1 else None

            if branch:
                run_cmd("git fetch origin {}:{} ".format(branch, branch))
            else:
                color_print("This option need a branch name.", TermColor.Red)

        @staticmethod
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
            email_re = re.compile(
                r"^[0-9a-zA-Z_]{0,19}@[0-9a-zA-Z]{1,13}\.[com,cn,net]{1,3}$"
            )
            while True:
                if email_re.match(email) is None:
                    color_print("Bad mailbox format.", TermColor.Red)
                    email = input("Please input email again:")
                else:
                    break

            if run_cmd(
                GitProcessor.Git_Options["user"]["command"] + other + name
            ) and run_cmd(GitProcessor.Git_Options["email"]["command"] + other + email):
                color_print("Successfully set.", TermColor.Green)
            else:
                color_print("Failed. Please check log.", TermColor.Red)

    Git_Options = {
        # Branch
        "b": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git branch ",
            "help-msg": "lists, creates, renames, and deletes branches.",
        },
        "bc": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git checkout -b ",
            "help-msg": "creates a new branch.",
        },
        "bl": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git branch -vv ",
            "help-msg": "lists branches and their commits.",
        },
        "bL": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git branch --all -vv ",
            "help-msg": "lists local and remote branches and their commits.",
        },
        "bs": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git show-branch ",
            "help-msg": "lists branches and their commits with ancestry graphs.",
        },
        "bS": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git show-branch --all ",
            "help-msg": "lists local and remote branches and their commits with ancestry graphs.",
        },
        "bm": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git branch --move ",
            "help-msg": "renames a branch.",
        },
        "bM": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git branch --move --force ",
            "help-msg": "renames a branch even if the new branch name already exists.",
        },
        # Commit
        "c": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git commit --verbose ",
            "help-msg": "records changes to the repository.",
        },
        "ca": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git commit --verbose --all ",
            "help-msg": "commits all modified and deleted files.",
        },
        "cA": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git commit --verbose --patch ",
            "help-msg": "commits all modified and deleted files interactively",
        },
        "cm": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git commit --verbose --message ",
            "help-msg": "commits with the given message.",
        },
        "co": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git checkout ",
            "help-msg": "checks out a branch or paths to the working tree.",
        },
        "cO": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git checkout --patch ",
            "help-msg": "checks out hunks from the index or the tree interactively.",
        },
        "cf": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git commit --amend --reuse-message HEAD ",
            "help-msg": "amends the tip of the current branch reusing the same log message as HEAD.",
        },
        "cF": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git commit --verbose --amend ",
            "help-msg": "amends the tip of the current branch.",
        },
        "cr": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git revert ",
            "help-msg": "reverts existing commits by reverting patches and recording new commits.",
        },
        "cR": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": 'git reset "HEAD^" ',
            "help-msg": "removes the HEAD commit.",
        },
        "cs": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": 'git show --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B"',
            "help-msg": "shows one or more objects (blobs, trees, tags and commits).",
        },
        # Conflict(C)
        "Cl": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git --no-pager diff --diff-filter=U --name-only ",
            "help-msg": "lists unmerged files.",
        },
        "Ca": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git add git --no-pager diff --diff-filter=U --name-only ",
            "help-msg": "adds unmerged file contents to the index.",
        },
        "Ce": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git mergetool git --no-pager diff --diff-filter=U --name-only ",
            "help-msg": "executes merge-tool on all unmerged files.",
        },
        "Co": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git checkout --ours -- ",
            "help-msg": "checks out our changes for unmerged paths.",
        },
        "CO": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git checkout --ours -- git --no-pager diff --diff-filter=U --name-only ",
            "help-msg": "checks out our changes for all unmerged paths.",
        },
        "Ct": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git checkout --theirs -- ",
            "help-msg": "checks out their changes for unmerged paths.",
        },
        "CT": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git checkout --theirs -- git --no-pager diff --diff-filter=U --name-only ",
            "help-msg": "checks out their changes for all unmerged paths.",
        },
        # Fetch(f)
        "f": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git fetch ",
            "help-msg": "downloads objects and references from another repository.",
        },
        "fc": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git clone ",
            "help-msg": "clones a repository into a new directory.",
        },
        "fC": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git clone --depth=1 ",
            "help-msg": "clones a repository into a new directory clearly(depth:1).",
        },
        "fm": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git pull ",
            "help-msg": "fetches from and merges with another repository or local branch.",
        },
        "fr": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git pull --rebase ",
            "help-msg": "fetches from and rebase on top of another repository or local branch.",
        },
        "fu": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git fetch --all --prune && git merge --ff-only @{u} ",
            "help-msg": "removes un-existing remote-tracking references, fetches all remotes and merges.",
        },
        "fb": {
            "state": GitOptionSign.Func | GitOptionSign.No,
            "command": _Function.fetch_remote_branch,
            "help-msg": "fetch other branch to local as same name.",
        },
        # Index(i)
        "i": {
            "state": GitOptionSign.Func | GitOptionSign.No,
            "command": InteractiveAdd(
                # use_color=CONFIG.gitprocessor_interactive_color,
                # help_wait=CONFIG.gitprocessor_interactive_help_showtime,
            ).add_interactive,
            "help-msg": "interactive operation git tree status.",
        },
        "ia": {
            "state": GitOptionSign.Func | GitOptionSign.Multi,
            "command": _Function.add,
            "help-msg": "adds file contents to the index(default: all files).",
        },
        "iA": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git add --patch ",
            "help-msg": "adds file contents to the index interactively.",
        },
        "iu": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git add --update ",
            "help-msg": "adds file contents to the index (updates only known files).",
        },
        "id": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git diff --no-ext-diff --cached ",
            "help-msg": "displays changes between the index and a named commit (diff).",
        },
        "iD": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git diff --no-ext-diff --cached --word-diff ",
            "help-msg": "displays changes between the index and a named commit (word diff).",
        },
        "ir": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git reset ",
            "help-msg": "resets the current HEAD to the specified state.",
        },
        "iR": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git reset --patch ",
            "help-msg": "resets the current index interactively.",
        },
        "ix": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git rm --cached -r ",
            "help-msg": "removes files from the index (recursively).",
        },
        "iX": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git rm --cached -rf ",
            "help-msg": "removes files from the index (recursively and forced).",
        },
        # Log(l)
        "l": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git log --graph --all --decorate ",
            "help-msg": "displays the log with good format.",
        },
        "l1": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git log --graph --all --decorate --oneline ",
            "help-msg": "",
        },
        "ls": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": 'git log --topo-order --stat --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B" ',
            "help-msg": "displays the stats log.",
        },
        "ld": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": 'git log --topo-order --stat --patch --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B" ',
            "help-msg": "displays the diff log.",
        },
        "lv": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": 'git log --topo-order --show-signature --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B" ',
            "help-msg": "displays the log, verifying the GPG signature of commits.",
        },
        "lc": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git shortlog --summary --numbered ",
            "help-msg": "displays the commit count for each contributor in descending order.",
        },
        "lr": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git reflog ",
            "help-msg": "manages reflog information.",
        },
        # Merge(m)
        "m": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git merge ",
            "help-msg": "joins two or more development histories together.",
        },
        "ma": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git merge --abort ",
            "help-msg": "aborts the conflict resolution, and reconstructs the pre-merge state.",
        },
        "mC": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git merge --no-commit ",
            "help-msg": "performs the merge but does not commit.",
        },
        "mF": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git merge --no-ff ",
            "help-msg": "creates a merge commit even if the merge could be resolved as a fast-forward.",
        },
        "mS": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git merge -S ",
            "help-msg": "performs the merge and GPG-signs the resulting commit.",
        },
        "mv": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git merge --verify-signatures ",
            "help-msg": "verifies the GPG signature of the tip commit of the side branch being merged.",
        },
        "mt": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git mergetool ",
            "help-msg": "runs the merge conflict resolution tools to resolve conflicts.",
        },
        # Push(p)
        "p": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git push ",
            "help-msg": "updates remote refs along with associated objects.",
        },
        "pf": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git push --force-with-lease ",
            "help-msg": 'forces a push safely (with "lease").',
        },
        "pF": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git push --force ",
            "help-msg": "forces a push. ",
        },
        "pa": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git push --all ",
            "help-msg": "pushes all branches.",
        },
        "pA": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git push --all && git push --tags ",
            "help-msg": "pushes all branches and tags.",
        },
        "pt": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git push --tags ",
            "help-msg": "pushes all tags.",
        },
        "pc": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": 'git push --set-upstream origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" ',
            "help-msg": "pushes the current branch and adds origin as an upstream reference for it.",
        },
        "pp": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": 'git pull origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" && git push origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" ',
            "help-msg": "pulls and pushes the current branch from origin to origin.",
        },
        # Remote(R)
        "R": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote ",
            "help-msg": "manages tracked repositories.",
        },
        "Rl": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote --verbose ",
            "help-msg": "lists remote names and their URLs.",
        },
        "Ra": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote add ",
            "help-msg": "adds a new remote.",
        },
        "Rx": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote rm ",
            "help-msg": "removes a remote.",
        },
        "Rm": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote rename ",
            "help-msg": "renames a remote.",
        },
        "Ru": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote update ",
            "help-msg": "fetches remotes updates.",
        },
        "Rp": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote prune ",
            "help-msg": "prunes all stale remote tracking branches.",
        },
        "Rs": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote show ",
            "help-msg": "shows information about a given remote.",
        },
        "RS": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote set-url ",
            "help-msg": "changes URLs for a remote.",
        },
        # Stash(s)
        "s": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git stash ",
            "help-msg": "stashes the changes of the dirty working directory.",
        },
        "sp": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git stash pop ",
            "help-msg": "removes and applies a single stashed state from the stash list.",
        },
        "sl": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git stash list ",
            "help-msg": "lists stashed states.",
        },
        "sd": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git stash show",
            "help-msg": "",
        },
        "sD": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git stash show --patch --stat",
            "help-msg": "",
        },
        # 'sr': {
        #     'state': GitOptionState.STRING | GitOptionState.MULTI,
        #     'command': '_git_stash_recover ',
        #     'help-msg': '',
        # },
        # 'sc': {
        #     'state': GitOptionState.STRING | GitOptionState.MULTI,
        #     'command': '_git_clear_stash_interactive',
        #     'help-msg': '',
        # },
        # Tag (t)
        "t": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git tag ",
            "help-msg": "creates, lists, deletes or verifies a tag object signed with GPG.",
        },
        "ta": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git tag -a ",
            "help-msg": "create a new tag.",
        },
        "tx": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git tag --delete ",
            "help-msg": "deletes tags with given names.",
        },
        # Working tree(w)
        "ws": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git status --short ",
            "help-msg": "displays working-tree status in the short format.",
        },
        "wS": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git status ",
            "help-msg": "displays working-tree status.",
        },
        "wd": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git diff --no-ext-diff ",
            "help-msg": "displays changes between the working tree and the index (diff).",
        },
        "wD": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git diff --no-ext-diff --word-diff ",
            "help-msg": "displays changes between the working tree and the index (word diff).",
        },
        "wr": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git reset --soft ",
            "help-msg": "resets the current HEAD to the specified state, does not touch the index nor the working tree.",
        },
        "wR": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git reset --hard ",
            "help-msg": "resets the current HEAD, index and working tree to the specified state.",
        },
        "wc": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git clean --dry-run ",
            "help-msg": "cleans untracked files from the working tree (dry-run).",
        },
        "wC": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git clean -d --force ",
            "help-msg": "cleans untracked files from the working tree.",
        },
        "wm": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git mv ",
            "help-msg": "moves or renames files.",
        },
        "wM": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git mv -f ",
            "help-msg": "moves or renames files (forced).",
        },
        "wx": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git rm -r ",
            "help-msg": "removes files from the working tree and from the index (recursively).",
        },
        "wX": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git rm -rf ",
            "help-msg": "removes files from the working tree and from the index (recursively and forced).",
        },
        # Setting
        "savepd": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git config credential.helper store ",
            "help-msg": "Remember your account and password.",
        },
        "ue": {
            "state": GitOptionSign.Func | GitOptionSign.Multi,
            "command": _Function.set_email_and_username,
            "help-msg": "set email and username interactively.",
        },
        "user": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git config user.name ",
            "help-msg": "set username.",
        },
        "email": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git config user.email ",
            "help-msg": "set user email.",
        },
        # 'clear': {
        #     'state': GitOptionState.STRING | GitOptionState.MULTI,
        #     'command': '_git_clear ${@:2:$((${#@}))} ',
        #     'help-msg': '',
        # },
        # 'ignore': {
        #     'state': GitOptionState.STRING | GitOptionState.MULTI,
        #     'command': '_git_ignore_files ${@:2:$((${#@}))} ',
        #     'help-msg': '',
        # },
    }

    @staticmethod
    def color_command(command):
        """Color the command string.
        prog: green;
        short command: yellow;
        arguments: skyblue;
        values: white.

        Args:
            command(str): valid command string.

        Returns:
            (str): color command string.
        """

        command_list = command.split(" ")
        color_command = (
            Fx.bold
            + TermColor.DeepGreen
            + command_list.pop(0)
            + " "
            + TermColor.Yellow
            + command_list.pop(0)
            + " "
            + Fx.unbold
            + Fx.italic
            + TermColor.SkyBlue
        )
        while len(command_list) > 0:
            temp = command_list.pop(0)
            if temp.startswith("-"):
                color_command += temp + " "
            else:
                break

        color_command += Fx.reset
        if len(command_list) > 0:
            color_command += " ".join(command_list)

        return color_command

    @classmethod
    def process_command(
        cls, _command, args=None, use_recommend=False, show_original=True
    ):
        """Process command and arguments.

        Args:
            _command (str): short command string
            args (list|None, optional): command arguments. Defaults to None.

        Raises:
            SystemExit: not git.
            SystemExit: short command not right.
        """

        if Git_Version is None:
            color_print("Git is not detected. Please install Git first.", TermColor.Red)
            raise SystemExit(0)

        option = cls.Git_Options.get(_command, None)

        if option is None:
            print("Don't support this command, please try ", end="")
            color_print("g --show-commands", TermColor.Gold)

            if use_recommend:  # check config.
                predicted_command = similar_command(_command, cls.Git_Options.keys())
                print(
                    "%s The wanted command is %s ?"
                    % (
                        Emotion.Icon_Thinking,
                        TermColor.Green + predicted_command + Fx.reset,
                    ),
                    end="",
                )
                if confirm("[y/n]:"):
                    cls.process_command(predicted_command, args=args)

            raise SystemExit(0)

        state = option.get("state", None)
        command = option.get("command", None)

        if state & GitOptionSign.No:
            if args:
                color_print(
                    "The command does not accept parameters. Discard {}.".format(args),
                    TermColor.Red,
                )
                args = []

        if state & GitOptionSign.Func:
            try:
                command(args)
            except TermError as e:
                color_print(str(e), TermColor.Red)
        elif state & GitOptionSign.String:
            if args:
                args_str = " ".join(args)
                command = " ".join([command, args_str])
            if show_original:
                print("{}  ".format(Emotion.Icon_Rainbow), end="")
                print(cls.color_command(command))
            run_cmd(command)
        else:
            pass

    ################################
    # Print command help message.
    ################################
    @classmethod
    def _generate_help_by_key(cls, _key, use_color=True):
        """Generate one help by given key.

        Args:
            _key (str): Short command string.
            use_color (bool, optional): Wether color help message. Defaults to True.

        Returns:
            (str): Help message of one command.
        """

        _msg = "    {key_color}{:<9}{reset}{}{command_color}{}{reset}"
        if use_color:
            _key_color = TermColor.Green
            _command_color = TermColor.Gold
        else:
            _key_color = _command_color = ""

        # Get help message and command.
        _help = cls.Git_Options[_key]["help-msg"]
        _command = cls.Git_Options[_key]["command"]

        # Process help.
        _help = _help + "\n" if _help else ""

        # Process command.
        if callable(_command):
            _command = "Callable: %s" % _command.__name__

        _command = shorten(_command, 70, placeholder="...")
        _command = " " * 13 + _command if _help else _command

        # Splicing and return.
        return _msg.format(
            _key,
            _help,
            _command,
            key_color=_key_color,
            command_color=_command_color,
            reset=Fx.reset,
        )

    @classmethod
    def command_help(cls):
        """Print help message."""
        print("These are short commands that can replace git operations:")
        for key in cls.Git_Options.keys():
            msg = cls._generate_help_by_key(key)
            print(msg)

    @classmethod
    def command_help_by_type(cls, command_type, use_recommend=False):
        """Print a part of help message.

        Print the help information of the corresponding part according to the
        incoming command type string. If there is no print error prompt for the
        type.

        Args:
            command_type (str): A command type of `TYPE`.
        """

        # Process received type.
        command_type = command_type.capitalize().strip()

        if command_type not in cls.Types:
            color_print("There is no such type.", TermColor.Red)
            print("Please use `", end="")
            print("g --types", TermColor.Green, end="")
            print(
                "` to view the supported types.",
            )
            if use_recommend:
                predicted_type = similar_command(command_type, cls.Types)
                print(
                    "%s The wanted type is %s ?"
                    % (
                        Emotion.Icon_Thinking,
                        TermColor.Green + predicted_type + Fx.reset,
                    ),
                    end="",
                )
                if confirm("[y/n]:"):
                    cls.command_help_by_type(predicted_type)
            raise SystemExit(0)

        print("These are the orders of {}".format(command_type))
        prefix = command_type[0].lower()
        for k in cls.Git_Options.keys():
            if k.startswith(prefix):
                msg = cls._generate_help_by_key(k)
                print(msg)

    @classmethod
    def type_help(cls):
        """Print all command types with random color."""
        for t in cls.Types:
            print(
                "{}{}  ".format(
                    Color.fg(
                        random.randint(70, 255),
                        random.randint(70, 255),
                        random.randint(70, 255),
                    ),
                    t,
                ),
                end="",
            )
        print(Fx.reset)
