# -*- coding:utf-8 -*-

"""Git optional short command dictionary.

The key is a short command, and the value is the information dictionary of the
short command.

[belong] is the type of command. The default is `Extra`.
[command] is the execution content of the short command. It supports (method, command
          string). The default is command.
[help] is help information, optional.
[has_arguments] indicates whether the short command receives parameters. The default is False.
"""

import enum
from ._cmd_func import *


@enum.unique
class CommandType(enum.Enum):
    Branch = "Branch"
    Commit = "Commit"
    Conflict = "Conflict"
    Fetch = "Fetch"
    Index = "Index"
    Log = "Log"
    Merge = "Merge"
    Push = "Push"
    Remote = "Remote"
    Stash = "Stash"
    Tag = "Tag"
    WorkingTree = "Working tree"
    Submodule = "Submodule"
    Setting = "Setting"
    Extra = "Extra"  # default


# The custom git output format string.
#   git ... --pretty={0}.format(GIT_PRINT_FORMAT)
_GIT_PRINT_FORMAT = (
    'format:"%C(bold yellow)commit %H%C(auto)%d%n'
    "%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n"
    '%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B"'
)


GIT_CMDS = {
    # Branch
    "b": {
        "belong": CommandType.Branch,
        "command": "git branch",
        "help": "lists, creates, renames, and deletes branches.",
        "has_arguments": True,
    },
    "bc": {
        "belong": CommandType.Branch,
        "command": "git checkout -b",
        "help": "creates a new branch.",
        "has_arguments": True,
    },
    "bl": {
        "belong": CommandType.Branch,
        "command": "git branch -vv",
        "help": "lists branches and their commits.",
    },
    "bL": {
        "belong": CommandType.Branch,
        "command": "git branch --all -vv",
        "help": "lists local and remote branches and their commits.",
    },
    "bs": {
        "belong": CommandType.Branch,
        "command": "git show-branch",
        "help": "lists branches and their commits with ancestry graphs.",
    },
    "bS": {
        "belong": CommandType.Branch,
        "command": "git show-branch --all",
        "help": "lists local and remote branches and their commits with "
        "ancestry graphs.",
    },
    "bm": {
        "belong": CommandType.Branch,
        "command": "git branch --move",
        "help": "renames a branch.",
        "has_arguments": True,
    },
    "bM": {
        "belong": CommandType.Branch,
        "command": "git branch --move --force",
        "help": "renames a branch even if the new branch name already exists.",
        "has_arguments": True,
    },
    "bd": {
        "belong": CommandType.Branch,
        "command": "git branch -d",
        "help": "delete a local branch by name.",
        "has_arguments": True,
    },
    # Commit
    "c": {
        "belong": CommandType.Commit,
        "command": "git commit --verbose",
        "help": "records changes to the repository.",
    },
    "ca": {
        "belong": CommandType.Commit,
        "command": "git commit --verbose --all",
        "help": "commits all modified and deleted files.",
    },
    "cA": {
        "belong": CommandType.Commit,
        "command": "git commit --verbose --patch",
        "help": "commits all modified and deleted files interactively",
    },
    "cm": {
        "belong": CommandType.Commit,
        "command": "git commit --verbose --message",
        "help": "commits with the given message.",
    },
    "co": {
        "belong": CommandType.Commit,
        "command": "git checkout",
        "help": "checks out a branch or paths to the working tree.",
        "has_arguments": True,
    },
    "cO": {
        "belong": CommandType.Commit,
        "command": "git checkout --patch",
        "help": "checks out hunks from the index or the tree interactively.",
        "has_arguments": True,
    },
    "cf": {
        "belong": CommandType.Commit,
        "command": "git commit --amend --reuse-message HEAD ",
        "help": "amends the tip of the current branch reusing the same log "
        "message as HEAD.",
    },
    "cF": {
        "belong": CommandType.Commit,
        "command": "git commit --verbose --amend",
        "help": "amends the tip of the current branch.",
    },
    "cr": {
        "belong": CommandType.Commit,
        "command": "git revert",
        "help": "reverts existing commits by reverting patches and recording "
        "new commits.",
        "has_arguments": True,
    },
    "cR": {
        "belong": CommandType.Commit,
        "command": 'git reset "HEAD^"',
        "help": "removes the HEAD commit.",
    },
    "cs": {
        "belong": CommandType.Commit,
        "command": f"git show --pretty={_GIT_PRINT_FORMAT}",
        "help": "shows one or more objects (blobs, trees, tags and commits).",
        "has_arguments": True,
    },
    # Conflict(C)
    "Cl": {
        "belong": CommandType.Conflict,
        "command": "git --no-pager diff --diff-filter=U --name-only",
        "help": "lists unmerged files.",
    },
    "Ca": {
        "belong": CommandType.Conflict,
        "command": "git add git --no-pager diff --diff-filter=U --name-only",
        "help": "adds unmerged file contents to the index.",
        "has_arguments": True,
    },
    "Ce": {
        "belong": CommandType.Conflict,
        "command": "git mergetool git --no-pager diff --diff-filter=U --name-only",
        "help": "executes merge-tool on all unmerged files.",
    },
    "Co": {
        "belong": CommandType.Conflict,
        "command": "git checkout --ours -- ",
        "help": "checks out our changes for unmerged paths.",
    },
    "CO": {
        "belong": CommandType.Conflict,
        "command": "git checkout --ours -- git --no-pager diff --diff-filter=U --name-only",
        "help": "checks out our changes for all unmerged paths.",
    },
    "Ct": {
        "belong": CommandType.Conflict,
        "command": "git checkout --theirs -- ",
        "help": "checks out their changes for unmerged paths.",
    },
    "CT": {
        "belong": CommandType.Conflict,
        "command": "git checkout --theirs -- git --no-pager diff --diff-filter=U --name-only",
        "help": "checks out their changes for all unmerged paths.",
    },
    # Fetch(f)
    "f": {
        "belong": CommandType.Fetch,
        "command": "git fetch",
        "help": "downloads objects and references from another repository.",
        "has_arguments": True,
    },
    "fc": {
        "belong": CommandType.Fetch,
        "command": "git clone",
        "help": "clones a repository into a new directory.",
        "has_arguments": True,
    },
    "fC": {
        "belong": CommandType.Fetch,
        "command": "git clone --depth=1",
        "help": "clones a repository into a new directory clearly(depth:1).",
        "has_arguments": True,
    },
    "fm": {
        "belong": CommandType.Fetch,
        "command": "git pull",
        "help": "fetches from and merges with another repository or local branch.",
        "has_arguments": True,
    },
    "fr": {
        "belong": CommandType.Fetch,
        "command": "git pull --rebase",
        "help": "fetches from and rebase on top of another repository or local branch.",
        "has_arguments": True,
    },
    "fu": {
        "belong": CommandType.Fetch,
        "command": "git fetch --all --prune && git merge --ff-only @{u}",
        "help": "removes un-existing remote-tracking references, fetches all remotes "
        "and merges.",
        "has_arguments": True,
    },
    "fb": {
        "belong": CommandType.Fetch,
        "command": fetch_remote_branch,
        "help": "fetch other branch to local as same name.",
    },
    # Index(i)
    "ia": {
        "belong": CommandType.Index,
        "command": add,
        "help": "adds file contents to the index(default: all files).",
        "has_arguments": True,
    },
    "iA": {
        "belong": CommandType.Index,
        "command": "git add --patch",
        "help": "adds file contents to the index interactively.",
        "has_arguments": True,
    },
    "iu": {
        "belong": CommandType.Index,
        "command": "git add --update",
        "help": "adds file contents to the index (updates only known files).",
        "has_arguments": True,
    },
    "id": {
        "belong": CommandType.Index,
        "command": "git diff --no-ext-diff --cached",
        "help": "displays changes between the index and a named commit (diff).",
        "has_arguments": True,
    },
    "iD": {
        "belong": CommandType.Index,
        "command": "git diff --no-ext-diff --cached --word-diff",
        "help": "displays changes between the index and a named commit (word diff).",
        "has_arguments": True,
    },
    "ir": {
        "belong": CommandType.Index,
        "command": "git reset",
        "help": "resets the current HEAD to the specified state.",
        "has_arguments": True,
    },
    "iR": {
        "belong": CommandType.Index,
        "command": "git reset --patch",
        "help": "resets the current index interactively.",
        "has_arguments": True,
    },
    "ix": {
        "belong": CommandType.Index,
        "command": "git rm --cached -r",
        "help": "removes files from the index (recursively).",
        "has_arguments": True,
    },
    "iX": {
        "belong": CommandType.Index,
        "command": "git rm --cached -rf",
        "help": "removes files from the index (recursively and forced).",
        "has_arguments": True,
    },
    # Log(l)
    "l": {
        "belong": CommandType.Log,
        "command": "git log --graph --all --decorate",
        "help": "display the log with good format.",
    },
    "l1": {
        "belong": CommandType.Log,
        "command": "git log --graph --all --decorate --oneline",
        "help": "display the log with oneline.",
    },
    "ls": {
        "belong": CommandType.Log,
        "command": f"git log --topo-order --stat --pretty={_GIT_PRINT_FORMAT}",
        "help": "displays the stats log.",
    },
    "ld": {
        "belong": CommandType.Log,
        "command": f"git log --topo-order --stat --patch --pretty={_GIT_PRINT_FORMAT}",
        "help": "displays the diff log.",
    },
    "lv": {
        "belong": CommandType.Log,
        "command": f"git log --topo-order --show-signature --pretty={_GIT_PRINT_FORMAT}",
        "help": "displays the log, verifying the GPG signature of commits.",
    },
    "lc": {
        "belong": CommandType.Log,
        "command": "git shortlog --summary --numbered",
        "help": "displays the commit count for each contributor in descending order.",
    },
    "lr": {
        "belong": CommandType.Log,
        "command": "git reflog",
        "help": "manages reflog information.",
        "has_arguments": True,
    },
    # Merge(m)
    "m": {
        "belong": CommandType.Merge,
        "command": "git merge",
        "help": "joins two or more development histories together.",
        "has_arguments": True,
    },
    "ma": {
        "belong": CommandType.Merge,
        "command": "git merge --abort",
        "help": "aborts the conflict resolution, and reconstructs the pre-merge state.",
        "has_arguments": True,
    },
    "mC": {
        "belong": CommandType.Merge,
        "command": "git merge --no-commit",
        "help": "performs the merge but does not commit.",
        "has_arguments": True,
    },
    "mF": {
        "belong": CommandType.Merge,
        "command": "git merge --no-ff",
        "help": "creates a merge commit even if the merge could be resolved as a "
        "fast-forward.",
        "has_arguments": True,
    },
    "mS": {
        "belong": CommandType.Merge,
        "command": "git merge -S",
        "help": "performs the merge and GPG-signs the resulting commit.",
        "has_arguments": True,
    },
    "mv": {
        "belong": CommandType.Merge,
        "command": "git merge --verify-signatures",
        "help": "verifies the GPG signature of the tip commit of the side branch "
        "being merged.",
        "has_arguments": True,
    },
    "mt": {
        "belong": CommandType.Merge,
        "command": "git mergetool",
        "help": "runs the merge conflict resolution tools to resolve conflicts.",
        "has_arguments": True,
    },
    # Push(p)
    "p": {
        "belong": CommandType.Push,
        "command": "git push",
        "help": "updates remote refs along with associated objects.",
        "has_arguments": True,
    },
    "pf": {
        "belong": CommandType.Push,
        "command": "git push --force-with-lease",
        "help": 'forces a push safely (with "lease").',
        "has_arguments": True,
    },
    "pF": {
        "belong": CommandType.Push,
        "command": "git push --force",
        "help": "forces a push.",
        "has_arguments": True,
    },
    "pa": {
        "belong": CommandType.Push,
        "command": "git push --all",
        "help": "pushes all branches.",
    },
    "pA": {
        "belong": CommandType.Push,
        "command": "git push --all && git push --tags",
        "help": "pushes all branches and tags.",
    },
    "pt": {
        "belong": CommandType.Push,
        "command": "git push --tags",
        "help": "pushes all tags.",
    },
    "pc": {
        "belong": CommandType.Push,
        "command": 'git push --set-upstream origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)"',
        "help": "pushes the current branch and adds origin as an upstream reference for it.",
    },
    "pp": {
        "belong": CommandType.Push,
        "command": (
            'git pull origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" && '
            'git push origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)"'
        ),
        "help": "pulls and pushes the current branch from origin to origin.",
    },
    # Remote(R)
    "R": {
        "belong": CommandType.Remote,
        "command": "git remote",
        "help": "manages tracked repositories.",
        "has_arguments": True,
    },
    "Rl": {
        "belong": CommandType.Remote,
        "command": "git remote --verbose",
        "help": "lists remote names and their URLs.",
        "has_arguments": True,
    },
    "Ra": {
        "belong": CommandType.Remote,
        "command": "git remote add",
        "help": "adds a new remote.",
        "has_arguments": True,
    },
    "Rx": {
        "belong": CommandType.Remote,
        "command": "git remote rm",
        "help": "removes a remote.",
        "has_arguments": True,
    },
    "Rm": {
        "belong": CommandType.Remote,
        "command": "git remote rename",
        "help": "renames a remote.",
        "has_arguments": True,
    },
    "Ru": {
        "belong": CommandType.Remote,
        "command": "git remote update",
        "help": "fetches remotes updates.",
        "has_arguments": True,
    },
    "Rp": {
        "belong": CommandType.Remote,
        "command": "git remote prune",
        "help": "prunes all stale remote tracking branches.",
        "has_arguments": True,
    },
    "Rs": {
        "belong": CommandType.Remote,
        "command": "git remote show",
        "help": "shows information about a given remote.",
        "has_arguments": True,
    },
    "RS": {
        "belong": CommandType.Remote,
        "command": "git remote set-url",
        "help": "changes URLs for a remote.",
        "has_arguments": True,
    },
    # Stash(s)
    "s": {
        "belong": CommandType.Stash,
        "command": "git stash",
        "help": "stashes the changes of the dirty working directory.",
        "has_arguments": True,
    },
    "sp": {
        "belong": CommandType.Stash,
        "command": "git stash pop",
        "help": "removes and applies a single stashed state from the stash list.",
    },
    "sl": {
        "belong": CommandType.Stash,
        "command": "git stash list",
        "help": "lists stashed states.",
    },
    "sd": {
        "belong": CommandType.Stash,
        "command": "git stash show",
        "help": "display stash list.",
        "has_arguments": True,
    },
    "sD": {
        "belong": CommandType.Stash,
        "command": "git stash show --patch --stat",
        "help": "display stash list with detail.",
        "has_arguments": True,
    },
    # Tag (t)
    "t": {
        "belong": CommandType.Tag,
        "command": "git tag",
        "help": "creates, lists, deletes or verifies a tag object signed with GPG.",
        "has_arguments": True,
    },
    "ta": {
        "belong": CommandType.Tag,
        "command": "git tag -a",
        "help": "create a new tag.",
        "has_arguments": True,
    },
    "tx": {
        "belong": CommandType.Tag,
        "command": "git tag --delete",
        "help": "deletes tags with given names.",
        "has_arguments": True,
    },
    # Working tree(w)
    "ws": {
        "belong": CommandType.WorkingTree,
        "command": "git status --short",
        "help": "displays working-tree status in the short format.",
    },
    "wS": {
        "belong": CommandType.WorkingTree,
        "command": "git status",
        "help": "displays working-tree status.",
        "has_arguments": True,
    },
    "wd": {
        "belong": CommandType.WorkingTree,
        "command": "git diff --no-ext-diff",
        "help": "displays changes between the working tree and the index (diff).",
        "has_arguments": True,
    },
    "wD": {
        "belong": CommandType.WorkingTree,
        "command": "git diff --no-ext-diff --word-diff",
        "help": "displays changes between the working tree and the index (word diff).",
        "has_arguments": True,
    },
    "wr": {
        "belong": CommandType.WorkingTree,
        "command": "git reset --soft",
        "help": "resets the current HEAD to the specified state, does not touch the "
        "index nor the working tree.",
        "has_arguments": True,
    },
    "wR": {
        "belong": CommandType.WorkingTree,
        "command": "git reset --hard",
        "help": "resets the current HEAD, index and working tree to the specified state.",
        "has_arguments": True,
    },
    "wc": {
        "belong": CommandType.WorkingTree,
        "command": "git clean --dry-run",
        "help": "cleans untracked files from the working tree (dry-run).",
        "has_arguments": True,
    },
    "wC": {
        "belong": CommandType.WorkingTree,
        "command": "git clean -d --force",
        "help": "cleans untracked files from the working tree.",
        "has_arguments": True,
    },
    "wm": {
        "belong": CommandType.WorkingTree,
        "command": "git mv",
        "help": "moves or renames files.",
        "has_arguments": True,
    },
    "wM": {
        "belong": CommandType.WorkingTree,
        "command": "git mv -f",
        "help": "moves or renames files (forced).",
        "has_arguments": True,
    },
    "wx": {
        "belong": CommandType.WorkingTree,
        "command": "git rm -r",
        "help": "removes files from the working tree and from the index (recursively).",
        "has_arguments": True,
    },
    "wX": {
        "belong": CommandType.WorkingTree,
        "command": "git rm -rf",
        "help": "removes files from the working tree and from the index (recursively "
        "and forced).",
        "has_arguments": True,
    },
    # Submodule
    "Sc": {
        "belong": CommandType.Submodule,
        "command": "git clone --recursive",
        "help": "Clone a repository as a submodule.",
        "has_arguments": True,
    },
    "Si": {
        "belong": CommandType.Submodule,
        "command": "git submodule update --init --recursive",
        "help": "Pull the submodule for the first time.",
    },
    # For above git 1.8.2
    #   `git submodule update --recursive --remote`
    # For above git 1.7.3
    #   `git submodule update --recursive`
    #   `git pull --reccurse-submodules`
    "Su": {
        "belong": CommandType.Submodule,
        "command": "git submodule update --recursive --remote",
        "help": "Update git submodule.",
    },
    "Sd": {
        "belong": CommandType.Submodule,
        "command": "git rm --cached",
        "help": "Remove submodule from repository.",
        "has_arguments": True,
    },
    "SD": {
        "belong": CommandType.Submodule,
        "command": "git submodule deinit",
        "help": "Inverse initialization submodule, clear the dir.",
        "has_arguments": True,
    },
    # Setting
    "savepd": {
        "belong": CommandType.Setting,
        "command": "git config credential.helper store",
        "help": "Remember your account and password.",
        "has_arguments": True,
    },
    "ue": {
        "belong": CommandType.Setting,
        "command": set_email_and_username,
        "help": "set email and username interactively.",
        "has_arguments": True,
    },
    "user": {
        "belong": CommandType.Setting,
        "command": "git config user.name",
        "help": "set username.",
        "has_arguments": True,
    },
    "email": {
        "belong": CommandType.Setting,
        "command": "git config user.email",
        "help": "set user email.",
        "has_arguments": True,
    },
}  # type: dict[str,dict]
