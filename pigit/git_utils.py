# -*- coding:utf-8 -*-

from typing import List, Optional, Tuple
import os, re, textwrap

from .common import exec_cmd
from .render import shorten, garbled_code_analysis
from .render.console import Console
from .git_model import File, Commit, Branch


#############
# Basic info
#############
def get_git_version() -> str:
    """Get Git version."""

    _, git_version_ = exec_cmd("git --version")
    return git_version_ or ""


def get_repo_info(
    given_path: Optional[str] = None, exclude_submodule: bool = False
) -> Tuple[str, str]:
    """
    Get the current git repository path. If not, the path is empty.
    Get the local git config path. If not, the path is empty.

    Return:
        (tuple[str, str]): repository path, git config path.
    """

    repo_path: str = ""
    git_conf_path: str = ""

    given_path = os.path.abspath(given_path or ".")
    if not os.path.isdir(given_path):
        return repo_path, git_conf_path

    err, repo_path = exec_cmd("git rev-parse --git-dir", cwd=given_path)
    if err:
        return repo_path, git_conf_path

    # remove useless space.
    repo_path = repo_path.strip()

    if ".git/submodule/" in repo_path and not exclude_submodule:
        # this repo is submodule.
        git_conf_path = repo_path
        repo_path = repo_path.replace("/.git/submodule/", "")
    elif repo_path == ".git":
        repo_path = given_path
        git_conf_path = os.path.join(repo_path, ".git")
    else:
        git_conf_path = repo_path
        repo_path = repo_path[:-5]

    return repo_path, git_conf_path


def get_repo_desc(
    include_part: Optional[List] = None, path: Optional[str] = None, color: bool = True
) -> str:
    """Return a string of repo various information.

    Args:
        include_part (Optional[list], optional): should return info part: [path,remote,branch,log,summary]. Defaults to None.
        path (Optional[str], optional): custom repo path. Defaults to None.
        color (bool, optional): whether return with color. Defaults to True.

    Returns:
        str:
    """

    error_str = "`Error getting.`<error>"
    gen = ["[b`Repository Information`]" if color else "[Repository Information]"]
    repo_path, _ = get_repo_info(path)

    # Get content.
    if not include_part or "path" in include_part:
        gen.append(
            f"Repository: \n\t`{repo_path}`<sky_blue>\n"
            if color
            else f"Repository: \n\t{repo_path}\n"
        )

    # Get remote url.
    if not include_part or "remote" in include_part:
        try:
            with open(f"{repo_path}/.git/config", "r") as cf:
                config = cf.read()
        except Exception:
            remote = error_str
        else:
            res = re.findall(r"url\s=\s(.*)", config)
            remote = "\n".join(
                [f"\ti`{x}`<sky_blue>" if color else f"\t{x}" for x in res]
            )
        gen.append("Remote: \n%s\n" % remote)

    # Get all branches.
    if not include_part or "branch" in include_part:
        err, res = exec_cmd(
            f"git branch --all --color={'always' if color else 'never'}"
        )
        branches = "\t" + error_str if err else textwrap.indent(res, "\t")
        gen.append("Branches: \n%s\n" % branches)

    # Get the lastest log.
    if not include_part or "log" in include_part:
        err, res = exec_cmd(
            f"git log --stat --oneline --decorate -1 --color={'always' if color else 'never'}"
        )
        git_log = "\t" + error_str if err else textwrap.indent(res, "\t")
        gen.append("Lastest log:\n%s\n" % git_log)

    # Get git summary.
    if not include_part or "summary" in include_part:
        err, res = exec_cmd(
            f"git shortlog --summary --numbered --color={'always' if color else 'never'}"
        )
        summary = "\t" + error_str if err else textwrap.indent(res, "\t")
        gen.append("Summary:\n%s\n" % summary)

    return "\n".join(gen)


def get_head(repo_path: Optional[str] = None):
    """Get current repo head. Return a branch name or a commit sha string."""

    _, res = exec_cmd(
        "git symbolic-ref -q --short HEAD || git describe --tags --exact-match",
        cwd=repo_path,
    )
    return res.rstrip()


def get_branches(repo_path: Optional[str] = None):
    """Get repo all branch."""

    err, branches = exec_cmd("git branch", cwd=repo_path)
    return branches


def get_remote(repo_path: Optional[str] = None):
    """Get repo remote url."""

    # Get remote name, exit when error.
    err, remote = exec_cmd("git remote show", cwd=repo_path)

    if err:
        return None

    remote = remote.strip().split("\n")[0]

    # Get remote url, exit when error.
    err, remote_url = exec_cmd(
        "git ls-remote --get-url {0}".format(remote), cwd=repo_path
    )

    if err:
        return None

    remote_url = remote_url[:-5]
    return remote_url


def get_first_pushed_commit(branch_name: str):
    command = "git merge-base %s %s@{u}" % (branch_name, branch_name)
    _, resp = exec_cmd(command)
    return resp.strip()


###############
# Special info
###############
def load_branches() -> List[Branch]:
    command = 'git branch --sort=-committerdate --format="%(HEAD)|%(refname:short)|%(upstream:short)|%(upstream:track)" '
    err, resp = exec_cmd(command)
    resp = resp.strip()

    if not resp:
        return []

    branchs = []
    lines = resp.split("\n")

    for line in lines:
        items = line.split("|")
        branch = Branch(
            name=items[1], pushables="?", pullables="?", is_head=items[0] == "*"
        )

        upstream_name = items[2]

        if not upstream_name:
            branchs.append(branch)
            continue

        branch.upstream_name = upstream_name

        track = items[3]
        _re = re.compile(r"ahead (\d+)")
        branch.pushables = str(match[1]) if (match := _re.search(track)) else "0"
        _re = re.compile(r"behind (\d+)")
        branch.pullables = str(match[1]) if (match := _re.search(track)) else "0"
        branchs.append(branch)

    return branchs


def load_log(branch_name: str, limit: bool = False, filter_path: str = "") -> Tuple:
    limit_flag = "-300" if limit else ""
    filter_flag = f"--follow -- {filter_path}" if filter_path else ""
    command = f'git log {branch_name} --oneline --pretty=format:"%H|%at|%aN|%d|%p|%s" {limit_flag} --abbrev=20 --date=unix {filter_flag}'
    err, resp = exec_cmd(command)
    return err, resp.strip()


def load_status(max_width: int, ident: int = 2, plain: bool = False) -> List[File]:
    """Get the file tree status of GIT for processing and encapsulation.
    Args:
        max_width (int): The max length of display string.
        ident (int, option): Number of reserved blank characters in the header.
    Raises:
        Exception: Can't get tree status.
    Returns:
        (list[File]): Processed file status list.
    """

    file_items = []
    err, files = exec_cmd("git status -s -u --porcelain")
    if err:
        raise Exception("Can't get git status.")
    for file in files.rstrip().split("\n"):
        # may is chinese char code.
        if file.endswith('"'):
            file = garbled_code_analysis(file)

        if not file.strip():
            # skip blank line.
            continue
        change = file[:2]
        staged_change = file[:1]
        unstaged_change = file[1:2]
        name = file[3:]
        untracked = change in ["??", "A ", "AM"]
        has_no_staged_change = staged_change in [" ", "U", "?"]
        has_merged_conflicts = change in ["DD", "AA", "UU", "AU", "UA", "UD", "DU"]
        has_inline_merged_conflicts = change in ["UU", "AA"]

        display_name = shorten(name, max_width - 3 - ident)
        # color full command.
        display_str = Console.render_str(
            f"`{staged_change}`<{'bad' if has_no_staged_change else'right'}>`{unstaged_change}`<{'bad' if unstaged_change!=' ' else'right'}> {display_name}"
        )

        file_ = File(
            name=name,
            display_str=display_str if not plain else file,
            short_status=change,
            has_staged_change=not has_no_staged_change,
            has_unstaged_change=unstaged_change != " ",
            tracked=not untracked,
            deleted=unstaged_change == "D" or staged_change == "D",
            added=unstaged_change == "A" or untracked,
            has_merged_conflicts=has_merged_conflicts,
            has_inline_merged_conflicts=has_inline_merged_conflicts,
        )
        file_items.append(file_)

    return file_items


def load_file_diff(
    file: str,
    tracked: bool = True,
    cached: bool = False,
    plain: bool = False,
    repo_path: str = None,
) -> str:
    """Gets the modification of the file.
    Args:
        file (str): file path relative to git.
        tracked (bool, optional): Defaults to True.
        cached (bool, optional): Defaults to False.
        plain (bool, optional): Whether need color. Defaults to False.
    Returns:
        (str): change string.
    """

    command = "git diff --submodule --no-ext-diff {plain} {cached} {tracked} {file}"

    _plain = "--color=never" if plain else "--color=always"

    _cached = "--cached" if cached else ""

    _tracked = "--no-index -- /dev/null" if not tracked else "--"

    if "->" in file:  # rename status.
        file = file.split("->")[-1].strip()

    err, res = exec_cmd(
        command.format(plain=_plain, cached=_cached, tracked=_tracked, file=file),
        cwd=repo_path,
    )
    if err:
        return "Can't get diff."
    return res.rstrip()


def load_commits(
    branch_name: str, limit: bool = True, filter_path: str = ""
) -> List[Commit]:
    """Get the all commit of a given branch.
    Args:
        branch_name (str): want branch name.
        limit (bool): Whether to get only the latest 300.
        filter_path (str): filter dir path, default is empty.
    """

    command = "git merge-base %s %s@{u}" % (branch_name, branch_name)
    _, resp = exec_cmd(command)
    first_pushed_commit = resp.strip()

    passed_first_pushed_commit = not first_pushed_commit
    commits: List[Commit] = []

    # Generate git command.
    limit_flag = "-300" if limit else ""
    filter_flag = f"--follow -- {filter_path}" if filter_path else ""
    command = f'git log {branch_name} --oneline --pretty=format:"%H|%at|%aN|%d|%p|%s" {limit_flag} --abbrev=20 --date=unix {filter_flag}'
    err, resp = exec_cmd(command)

    if err:
        return commits  # current is empty list.

    # Process data.
    for line in resp.split("\n"):
        split_ = line.split("|")

        sha = split_[0]
        unix_timestamp = int(split_[1])
        author = split_[2]
        extra_info = (split_[3]).strip()
        # parent_hashes = split_[4]
        message = "|".join(split_[5:])

        tag = []
        if extra_info:
            _re = re.compile(r"tag: ([^,\\]+)")
            if match := _re.search(extra_info):
                tag.append(match[1])

        if sha == first_pushed_commit:
            passed_first_pushed_commit = True
        status = {True: "unpushed", False: "pushed"}[not passed_first_pushed_commit]

        commit_ = Commit(
            sha=sha,
            msg=message,
            author=author,
            unix_timestamp=unix_timestamp,
            status=status,
            extra_info=extra_info,
            tag=tag,
        )
        commits.append(commit_)

    return commits


def load_commit_info(commit_sha: str, file_name: str = "", plain: bool = False) -> str:
    """Gets the change of a file or all in a given commit.
    Args:
        commit_sha: commit id.
        file_name: file name(include full path).
        plain: whether has color.
    """

    color_str = "never" if plain else "always"

    command = "git show --color=%s %s %s" % (color_str, commit_sha, file_name)
    _, resp = exec_cmd(command)
    return resp.rstrip()


##########
# Options
##########
def switch_file_status(file: File, repo_path: Optional[str] = None):
    if file.has_merged_conflicts or file.has_inline_merged_conflicts:
        pass
    elif file.has_unstaged_change:
        exec_cmd("git add -- {}".format(file.name), cwd=repo_path)
    elif file.has_staged_change:
        if file.tracked:
            exec_cmd("git reset HEAD -- {}".format(file.name), cwd=repo_path)
        else:
            exec_cmd("git rm --cached --force -- {}".format(file.name), cwd=repo_path)


def discard_file(file: File, repo_path: Optional[str] = None):
    if file.tracked:
        exec_cmd("git checkout -- {}".format(file.name), cwd=repo_path)
    else:
        os.remove(os.path.join(repo_path, file.name))


def ignore_file(file: File):
    """
    Args:
        f_path (str): full file path will be ignore.
    """
    with open(f"{get_repo_info()[0]}/.gitignore", "a+") as f:
        f.write(f"\n{file.name}")


def checkout_branch(branch_name: str):
    err, _ = exec_cmd(f"git checkout {branch_name}")
    if err:
        return err
