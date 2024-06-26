# -*- coding:utf-8 -*-

"""Git optional short command dictionary.

The key is a short command, and the value is the information dictionary of the
short command.

[belong] is the type of command. The default is `Extra`.
[command] is the execution content of the short command. It supports (method, command
          string). The default is command.
[help] is help information, optional.
[has_arguments] indicates whether the short command receives parameters. The default is False.

Example:
    "b": {
        "belong": CommandType.Branch,
        "command": "git branch",
        "help": "lists, creates, renames, and deletes branches.",
        "has_arguments": True,
    }
"""

from .define import GitCommandType, GitProxyOptionsGroup
from ._cmd_func import *


# The custom git output format string.
#   git ... --pretty={0}.format(GIT_PRINT_FORMAT)
_GIT_PRINT_FORMAT = (
    'format:"%C(bold yellow)commit %H%C(auto)%d%n'
    "%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n"
    '%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B"'
)

# Branch(b)
_branch_group: GitProxyOptionsGroup = {
    "b": {
        "belong": GitCommandType.Branch,
        "command": "git branch",
        "help": "lists, creates, renames, and deletes branches.",
        "has_arguments": True,
    },
    "bc": {
        "belong": GitCommandType.Branch,
        "command": "git checkout -b",
        "help": "creates a new branch.",
        "has_arguments": True,
    },
    "bl": {
        "belong": GitCommandType.Branch,
        "command": "git branch -vv",
        "help": "lists branches and their commits.",
    },
    "bL": {
        "belong": GitCommandType.Branch,
        "command": "git branch --all -vv",
        "help": "lists local and remote branches and their commits.",
    },
    "bs": {
        "belong": GitCommandType.Branch,
        "command": "git show-branch",
        "help": "lists branches and their commits with ancestry graphs.",
    },
    "bS": {
        "belong": GitCommandType.Branch,
        "command": "git show-branch --all",
        "help": "lists local and remote branches and their commits with "
        "ancestry graphs.",
    },
    "bm": {
        "belong": GitCommandType.Branch,
        "command": "git branch --move",
        "help": "renames a branch.",
        "has_arguments": True,
    },
    "bM": {
        "belong": GitCommandType.Branch,
        "command": "git branch --move --force",
        "help": "renames a branch even if the new branch name already exists.",
        "has_arguments": True,
    },
    "bd": {
        "belong": GitCommandType.Branch,
        "command": "git branch -d",
        "help": "delete a local branch by name.",
        "has_arguments": True,
    },
}

# Commit(c)
_commit_group: GitProxyOptionsGroup = {
    "c": {
        "belong": GitCommandType.Commit,
        "command": "git commit --verbose",
        "help": "records changes to the repository.",
    },
    "ca": {
        "belong": GitCommandType.Commit,
        "command": "git commit --verbose --all",
        "help": "commits all modified and deleted files.",
    },
    "cA": {
        "belong": GitCommandType.Commit,
        "command": "git commit --verbose --patch",
        "help": "commits all modified and deleted files interactively",
    },
    "cm": {
        "belong": GitCommandType.Commit,
        "command": "git commit --verbose --message",
        "help": "commits with the given message.",
    },
    "co": {
        "belong": GitCommandType.Commit,
        "command": "git checkout",
        "help": "checks out a branch or paths to the working tree.",
        "has_arguments": True,
    },
    "cO": {
        "belong": GitCommandType.Commit,
        "command": "git checkout --patch",
        "help": "checks out hunks from the index or the tree interactively.",
        "has_arguments": True,
    },
    "cf": {
        "belong": GitCommandType.Commit,
        "command": "git commit --amend --reuse-message HEAD ",
        "help": "amends the tip of the current branch reusing the same log "
        "message as HEAD.",
    },
    "cF": {
        "belong": GitCommandType.Commit,
        "command": "git commit --verbose --amend",
        "help": "amends the tip of the current branch.",
    },
    "cr": {
        "belong": GitCommandType.Commit,
        "command": "git revert",
        "help": "reverts existing commits by reverting patches and recording "
        "new commits.",
        "has_arguments": True,
    },
    "cR": {
        "belong": GitCommandType.Commit,
        "command": 'git reset "HEAD^"',
        "help": "removes the HEAD commit.",
    },
    "cs": {
        "belong": GitCommandType.Commit,
        "command": f"git show --pretty={_GIT_PRINT_FORMAT}",
        "help": "shows one or more objects (blobs, trees, tags and commits).",
        "has_arguments": True,
    },
}

# Conflict(C)
_conflict_group: GitProxyOptionsGroup = {
    "Cl": {
        "belong": GitCommandType.Conflict,
        "command": "git --no-pager diff --diff-filter=U --name-only",
        "help": "lists unmerged files.",
    },
    "Ca": {
        "belong": GitCommandType.Conflict,
        "command": "git add git --no-pager diff --diff-filter=U --name-only",
        "help": "adds unmerged file contents to the index.",
        "has_arguments": True,
    },
    "Ce": {
        "belong": GitCommandType.Conflict,
        "command": "git mergetool git --no-pager diff --diff-filter=U --name-only",
        "help": "executes merge-tool on all unmerged files.",
    },
    "Co": {
        "belong": GitCommandType.Conflict,
        "command": "git checkout --ours -- ",
        "help": "checks out our changes for unmerged paths.",
    },
    "CO": {
        "belong": GitCommandType.Conflict,
        "command": "git checkout --ours -- git --no-pager diff --diff-filter=U --name-only",
        "help": "checks out our changes for all unmerged paths.",
    },
    "Ct": {
        "belong": GitCommandType.Conflict,
        "command": "git checkout --theirs -- ",
        "help": "checks out their changes for unmerged paths.",
    },
    "CT": {
        "belong": GitCommandType.Conflict,
        "command": "git checkout --theirs -- git --no-pager diff --diff-filter=U --name-only",
        "help": "checks out their changes for all unmerged paths.",
    },
}

# Fetch(f)
_fetch_group: GitProxyOptionsGroup = {
    "f": {
        "belong": GitCommandType.Fetch,
        "command": "git fetch",
        "help": "downloads objects and references from another repository.",
        "has_arguments": True,
    },
    "fc": {
        "belong": GitCommandType.Fetch,
        "command": "git clone",
        "help": "clones a repository into a new directory.",
        "has_arguments": True,
    },
    "fC": {
        "belong": GitCommandType.Fetch,
        "command": "git clone --depth=1",
        "help": "clones a repository into a new directory clearly(depth:1).",
        "has_arguments": True,
    },
    "fm": {
        "belong": GitCommandType.Fetch,
        "command": "git pull",
        "help": "fetches from and merges with another repository or local branch.",
        "has_arguments": True,
    },
    "fr": {
        "belong": GitCommandType.Fetch,
        "command": "git pull --rebase",
        "help": "fetches from and rebase on top of another repository or local branch.",
        "has_arguments": True,
    },
    "fu": {
        "belong": GitCommandType.Fetch,
        "command": "git fetch --all --prune && git merge --ff-only @{u}",
        "help": "removes un-existing remote-tracking references, fetches all remotes "
        "and merges.",
        "has_arguments": True,
    },
    "fb": {
        "belong": GitCommandType.Fetch,
        "command": fetch_remote_branch,
        "help": "fetch other branch to local as same name.",
    },
}

# Index(i)
_index_group: GitProxyOptionsGroup = {
    "ia": {
        "belong": GitCommandType.Index,
        "command": add,
        "help": "adds file contents to the index(default: all files).",
        "has_arguments": True,
    },
    "iA": {
        "belong": GitCommandType.Index,
        "command": "git add --patch",
        "help": "adds file contents to the index interactively.",
        "has_arguments": True,
    },
    "iu": {
        "belong": GitCommandType.Index,
        "command": "git add --update",
        "help": "adds file contents to the index (updates only known files).",
        "has_arguments": True,
    },
    "id": {
        "belong": GitCommandType.Index,
        "command": "git diff --no-ext-diff --cached",
        "help": "displays changes between the index and a named commit (diff).",
        "has_arguments": True,
    },
    "iD": {
        "belong": GitCommandType.Index,
        "command": "git diff --no-ext-diff --cached --word-diff",
        "help": "displays changes between the index and a named commit (word diff).",
        "has_arguments": True,
    },
    "ir": {
        "belong": GitCommandType.Index,
        "command": "git reset",
        "help": "resets the current HEAD to the specified state.",
        "has_arguments": True,
    },
    "iR": {
        "belong": GitCommandType.Index,
        "command": "git reset --patch",
        "help": "resets the current index interactively.",
        "has_arguments": True,
    },
    "ix": {
        "belong": GitCommandType.Index,
        "command": "git rm --cached -r",
        "help": "removes files from the index (recursively).",
        "has_arguments": True,
    },
    "iX": {
        "belong": GitCommandType.Index,
        "command": "git rm --cached -rf",
        "help": "removes files from the index (recursively and forced).",
        "has_arguments": True,
    },
}

# Log(l)
_log_group: GitProxyOptionsGroup = {
    "l": {
        "belong": GitCommandType.Log,
        "command": "git log --graph --all --decorate",
        "help": "display the log with good format.",
    },
    "l1": {
        "belong": GitCommandType.Log,
        "command": "git log --graph --all --decorate --oneline",
        "help": "display the log with one-line.",
    },
    "ls": {
        "belong": GitCommandType.Log,
        "command": f"git log --topo-order --stat --pretty={_GIT_PRINT_FORMAT}",
        "help": "displays the stats log.",
    },
    "ld": {
        "belong": GitCommandType.Log,
        "command": f"git log --topo-order --stat --patch --pretty={_GIT_PRINT_FORMAT}",
        "help": "displays the diff log.",
    },
    "lv": {
        "belong": GitCommandType.Log,
        "command": f"git log --topo-order --show-signature --pretty={_GIT_PRINT_FORMAT}",
        "help": "displays the log, verifying the GPG signature of commits.",
    },
    "lc": {
        "belong": GitCommandType.Log,
        "command": "git shortlog --summary --numbered",
        "help": "displays the commit count for each contributor in descending order.",
    },
    "lr": {
        "belong": GitCommandType.Log,
        "command": "git reflog",
        "help": "manages reflog information.",
        "has_arguments": True,
    },
}

# Merge(m)
_merge_group: GitProxyOptionsGroup = {
    "m": {
        "belong": GitCommandType.Merge,
        "command": "git merge",
        "help": "joins two or more development histories together.",
        "has_arguments": True,
    },
    "ma": {
        "belong": GitCommandType.Merge,
        "command": "git merge --abort",
        "help": "aborts the conflict resolution, and reconstructs the pre-merge state.",
        "has_arguments": True,
    },
    "mC": {
        "belong": GitCommandType.Merge,
        "command": "git merge --no-commit",
        "help": "performs the merge but does not commit.",
        "has_arguments": True,
    },
    "mF": {
        "belong": GitCommandType.Merge,
        "command": "git merge --no-ff",
        "help": "creates a merge commit even if the merge could be resolved as a "
        "fast-forward.",
        "has_arguments": True,
    },
    "mS": {
        "belong": GitCommandType.Merge,
        "command": "git merge -S",
        "help": "performs the merge and GPG-signs the resulting commit.",
        "has_arguments": True,
    },
    "mv": {
        "belong": GitCommandType.Merge,
        "command": "git merge --verify-signatures",
        "help": "verifies the GPG signature of the tip commit of the side branch "
        "being merged.",
        "has_arguments": True,
    },
    "mt": {
        "belong": GitCommandType.Merge,
        "command": "git mergetool",
        "help": "runs the merge conflict resolution tools to resolve conflicts.",
        "has_arguments": True,
    },
}

# Push(p)
_push_group: GitProxyOptionsGroup = {
    "p": {
        "belong": GitCommandType.Push,
        "command": "git push",
        "help": "updates remote refs along with associated objects.",
        "has_arguments": True,
    },
    "pf": {
        "belong": GitCommandType.Push,
        "command": "git push --force-with-lease",
        "help": 'forces a push safely (with "lease").',
        "has_arguments": True,
    },
    "pF": {
        "belong": GitCommandType.Push,
        "command": "git push --force",
        "help": "forces a push.",
        "has_arguments": True,
    },
    "pa": {
        "belong": GitCommandType.Push,
        "command": "git push --all",
        "help": "pushes all branches.",
    },
    "pA": {
        "belong": GitCommandType.Push,
        "command": "git push --all && git push --tags",
        "help": "pushes all branches and tags.",
    },
    "pt": {
        "belong": GitCommandType.Push,
        "command": "git push --tags",
        "help": "pushes all tags.",
    },
    "pc": {
        "belong": GitCommandType.Push,
        "command": 'git push --set-upstream origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)"',
        "help": "pushes the current branch and adds origin as an upstream reference for it.",
    },
    "pp": {
        "belong": GitCommandType.Push,
        "command": (
            'git pull origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" && '
            'git push origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)"'
        ),
        "help": "pulls and pushes the current branch from origin to origin.",
    },
}

# Remote(R)
_remote_group: GitProxyOptionsGroup = {
    "R": {
        "belong": GitCommandType.Remote,
        "command": "git remote",
        "help": "manages tracked repositories.",
        "has_arguments": True,
    },
    "Rl": {
        "belong": GitCommandType.Remote,
        "command": "git remote --verbose",
        "help": "lists remote names and their URLs.",
        "has_arguments": True,
    },
    "Ra": {
        "belong": GitCommandType.Remote,
        "command": "git remote add",
        "help": "adds a new remote.",
        "has_arguments": True,
    },
    "Rx": {
        "belong": GitCommandType.Remote,
        "command": "git remote rm",
        "help": "removes a remote.",
        "has_arguments": True,
    },
    "Rm": {
        "belong": GitCommandType.Remote,
        "command": "git remote rename",
        "help": "renames a remote.",
        "has_arguments": True,
    },
    "Ru": {
        "belong": GitCommandType.Remote,
        "command": "git remote update",
        "help": "fetches remotes updates.",
        "has_arguments": True,
    },
    "Rp": {
        "belong": GitCommandType.Remote,
        "command": "git remote prune",
        "help": "prunes all stale remote tracking branches.",
        "has_arguments": True,
    },
    "Rs": {
        "belong": GitCommandType.Remote,
        "command": "git remote show",
        "help": "shows information about a given remote.",
        "has_arguments": True,
    },
    "RS": {
        "belong": GitCommandType.Remote,
        "command": "git remote set-url",
        "help": "changes URLs for a remote.",
        "has_arguments": True,
    },
}

# Stash(s)
_stash_group: GitProxyOptionsGroup = {
    "s": {
        "belong": GitCommandType.Stash,
        "command": "git stash",
        "help": "stashes the changes of the dirty working directory.",
        "has_arguments": True,
    },
    "sp": {
        "belong": GitCommandType.Stash,
        "command": "git stash pop",
        "help": "removes and applies a single stashed state from the stash list.",
    },
    "sl": {
        "belong": GitCommandType.Stash,
        "command": "git stash list",
        "help": "lists stashed states.",
    },
    "sd": {
        "belong": GitCommandType.Stash,
        "command": "git stash show",
        "help": "display stash list.",
        "has_arguments": True,
    },
    "sD": {
        "belong": GitCommandType.Stash,
        "command": "git stash show --patch --stat",
        "help": "display stash list with detail.",
        "has_arguments": True,
    },
}

# Tag (t)
_tag_group: GitProxyOptionsGroup = {
    "t": {
        "belong": GitCommandType.Tag,
        "command": "git tag",
        "help": "creates, lists, deletes or verifies a tag object signed with GPG.",
        "has_arguments": True,
    },
    "ta": {
        "belong": GitCommandType.Tag,
        "command": "git tag -a",
        "help": "create a new tag.",
        "has_arguments": True,
    },
    "tx": {
        "belong": GitCommandType.Tag,
        "command": "git tag --delete",
        "help": "deletes tags with given names.",
        "has_arguments": True,
    },
}

# Working tree(w)
_working_tree_group: GitProxyOptionsGroup = {
    "ws": {
        "belong": GitCommandType.WorkingTree,
        "command": "git status --short",
        "help": "displays working-tree status in the short format.",
    },
    "wS": {
        "belong": GitCommandType.WorkingTree,
        "command": "git status",
        "help": "displays working-tree status.",
        "has_arguments": True,
    },
    "wd": {
        "belong": GitCommandType.WorkingTree,
        "command": "git diff --no-ext-diff",
        "help": "displays changes between the working tree and the index (diff).",
        "has_arguments": True,
    },
    "wD": {
        "belong": GitCommandType.WorkingTree,
        "command": "git diff --no-ext-diff --word-diff",
        "help": "displays changes between the working tree and the index (word diff).",
        "has_arguments": True,
    },
    "wr": {
        "belong": GitCommandType.WorkingTree,
        "command": "git reset --soft",
        "help": "resets the current HEAD to the specified state, does not touch the "
        "index nor the working tree.",
        "has_arguments": True,
    },
    "wR": {
        "belong": GitCommandType.WorkingTree,
        "command": "git reset --hard",
        "help": "resets the current HEAD, index and working tree to the specified state.",
        "has_arguments": True,
    },
    "wc": {
        "belong": GitCommandType.WorkingTree,
        "command": "git clean --dry-run",
        "help": "cleans untracked files from the working tree (dry-run).",
        "has_arguments": True,
    },
    "wC": {
        "belong": GitCommandType.WorkingTree,
        "command": "git clean -d --force",
        "help": "cleans untracked files from the working tree.",
        "has_arguments": True,
    },
    "wm": {
        "belong": GitCommandType.WorkingTree,
        "command": "git mv",
        "help": "moves or renames files.",
        "has_arguments": True,
    },
    "wM": {
        "belong": GitCommandType.WorkingTree,
        "command": "git mv -f",
        "help": "moves or renames files (forced).",
        "has_arguments": True,
    },
    "wx": {
        "belong": GitCommandType.WorkingTree,
        "command": "git rm -r",
        "help": "removes files from the working tree and from the index (recursively).",
        "has_arguments": True,
    },
    "wX": {
        "belong": GitCommandType.WorkingTree,
        "command": "git rm -rf",
        "help": "removes files from the working tree and from the index (recursively "
        "and forced).",
        "has_arguments": True,
    },
}

# Submodule(S)
_submodule_group: GitProxyOptionsGroup = {
    "Sc": {
        "belong": GitCommandType.Submodule,
        "command": "git clone --recursive",
        "help": "Clone a repository as a submodule.",
        "has_arguments": True,
    },
    "Si": {
        "belong": GitCommandType.Submodule,
        "command": "git submodule update --init --recursive",
        "help": "Pull the submodule for the first time.",
    },
    # For above git 1.8.2
    #   `git submodule update --recursive --remote`
    # For above git 1.7.3
    #   `git submodule update --recursive`
    #   `git pull --reccurse-submodules`
    "Su": {
        "belong": GitCommandType.Submodule,
        "command": "git submodule update --recursive --remote",
        "help": "Update git submodule.",
    },
    "Sd": {
        "belong": GitCommandType.Submodule,
        "command": "git rm --cached",
        "help": "Remove submodule from repository.",
        "has_arguments": True,
    },
    "SD": {
        "belong": GitCommandType.Submodule,
        "command": "git submodule deinit",
        "help": "Inverse initialization submodule, clear the dir.",
        "has_arguments": True,
    },
}

Git_Proxy_Cmds: GitProxyOptionsGroup = {
    **_branch_group,
    **_commit_group,
    **_conflict_group,
    **_fetch_group,
    **_index_group,
    **_log_group,
    **_merge_group,
    **_push_group,
    **_remote_group,
    **_stash_group,
    **_tag_group,
    **_working_tree_group,
    **_submodule_group,
    # Setting
    "savepd": {
        "belong": GitCommandType.Setting,
        "command": "git config credential.helper store",
        "help": "Remember your account and password.",
        "has_arguments": True,
    },
    "ue": {
        "belong": GitCommandType.Setting,
        "command": set_email_and_username,
        "help": "set email and username interactively.",
        "has_arguments": True,
    },
    "user": {
        "belong": GitCommandType.Setting,
        "command": "git config user.name",
        "help": "set username.",
        "has_arguments": True,
    },
    "email": {
        "belong": GitCommandType.Setting,
        "command": "git config user.email",
        "help": "set user email.",
        "has_arguments": True,
    },
}
