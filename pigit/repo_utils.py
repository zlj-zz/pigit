import json
import os
import textwrap
from collections import Counter

from pigit.common import render_str, async_run_cmd, exec_async_tasks, exec_cmd, run_cmd
from pigit.const import REPOS_PATH
from pigit.git_utils import get_head, get_repo_info


def _make_repo_name(path: str, repos: list[str], name_counts: Counter) -> str:
    """
    Given a new repo `path`, create a repo name. By default, basename is used.
    If name collision exists, further include parent path name.

    Args:
        path (str): repo path.
        repos (list[str]): path list of exist repos.
        name_counts (Counter): generated default name.

    Returns:
        (str): final repo name.
    """

    name = os.path.basename(os.path.normpath(path))
    if name in repos or name_counts[name] > 1:
        # path has no trailing /
        par_name = os.path.basename(os.path.dirname(path))
        return os.path.join(par_name, name)
    return name


def load_repos() -> dict:
    if not os.path.isfile(REPOS_PATH):
        return {}

    with open(REPOS_PATH, "r") as fp:
        return json.load(fp)


def save_repos(repos: dict) -> bool:
    if not os.path.isfile(REPOS_PATH):
        os.makedirs(os.path.dirname(REPOS_PATH), exist_ok=True)

    try:
        with open(REPOS_PATH, "w+") as fp:
            json.dump(repos, fp, indent=2)
            return True
    except Exception:
        return False


def clear_repos():
    if os.path.isfile(REPOS_PATH):
        os.remove(REPOS_PATH)


def add_repos(paths: list[str], dry_run: bool = False, silent: bool = False):
    """
    Traverse the incoming paths. If it is not saved and is a git directory, add it to repos.

    Args:
        paths (list[str]): incoming paths.
        dry_run (bool, optional): Show but not really execute. Defaults to False.
        silent (bool, optional): No output. Defaults to False.
    """

    exist_repos = load_repos()
    exist_paths = [r["path"] for r in exist_repos.values()]

    new_git_paths = []
    for p in paths:
        repo_path, repo_conf = get_repo_info(p)
        if repo_path and repo_path not in exist_paths:
            new_git_paths.append(repo_path)

    if new_git_paths:
        not silent and print(f"Found {len(new_git_paths)} new repo(s).")
        for path in new_git_paths:
            not silent and print(render_str(f"`{path}`<sky_blue>"))

        if dry_run:
            return

        name_counts = Counter(
            os.path.basename(os.path.normpath(p)) for p in new_git_paths
        )
        new_repos = {
            _make_repo_name(path, exist_repos, name_counts): {"path": path}
            for path in new_git_paths
        }

        save_repos({**exist_repos, **new_repos})
    else:
        not silent and print(render_str("`No new repos found!`<tomato>"))


def rm_repos(repos: list[str], use_path: bool = False):
    exist_repos = load_repos()

    del_repos = []
    if use_path:
        for repo, v in exist_repos.items():
            if v["path"] in repos:
                del_repos.append(repo)
    else:
        for repo in repos:
            if exist_repos.get(repo, None):
                del_repos.append(repo)
            else:
                print(render_str(f"`No repo name is '{repo}'.`<tomato>"))

    for repo in del_repos:
        print(f"Deleted repo. name: '{repo}', path: {exist_repos[repo]['path']}")
        del exist_repos[repo]

    save_repos(exist_repos)


def rename_repo(repo, name):
    print(repo, name)
    exist_repos = load_repos()

    if name in exist_repos:
        print(f"'{name}' is already in use!")
    elif repo not in exist_repos:
        print(f"'{repo}' is not a valid repo name!")
    else:
        prop = exist_repos[repo]
        del exist_repos[repo]
        exist_repos[name] = prop

        save_repos(exist_repos)
        print(f"rename successful, `{repo}`->`{name}`.")


def ll_repos(simple: bool = False):
    exist_repos = load_repos()

    for repo_name, prop in exist_repos.items():
        head = get_head(repo_path=prop["path"])

        _, unstaged = exec_cmd("git diff --stat", cwd=prop["path"])
        _, staged = exec_cmd("git diff --stat --cached", cwd=prop["path"])
        _, untracked = exec_cmd("git ls-files -zo --exclude-standard", cwd=prop["path"])
        _, commit_hash = exec_cmd("git merge-base @{0} @{u}", cwd=prop["path"])
        _, commit = exec_cmd(
            "git log -1 --format='%s (%cd)||%C(auto)%d%n' --date=relative --color",
            cwd=prop["path"],
        )

        commit_msg, branch_status = commit.strip().split("||")
        unstaged_symbol = "*" if unstaged else " "
        staged_symbol = "+" if staged else " "
        untracked_symbol = "?" if untracked else " "

        if simple:
            print(
                f"{repo_name:<20} {head} {unstaged_symbol}{staged_symbol}{untracked_symbol}"
            )
        else:
            print(
                render_str(
                    textwrap.dedent(
                        f"""\
                    b`{repo_name}`
                        Branch: {head} {unstaged_symbol}{staged_symbol}{untracked_symbol}
                        Branch status: {branch_status}
                        Commit hash: `{commit_hash.strip()}`<khaki>
                        Commit msg: {commit_msg}
                        Path: `{prop['path']}`<sky_blue>
                    """
                    )
                )
            )


repo_options = {
    "fetch": {"cmd": "git fetch", "allow_all": True, "help": "fetch remote update"},
    "pull": {"cmd": "git pull", "allow_all": True, "help": "pull remote updates"},
    "push": {"cmd": "git push", "allow_all": True, "help": "push the local updates"},
}


def process_repo_option(repos, op):
    exist_repos = load_repos()

    if repos:
        exist_repos = {k: v for k, v in exist_repos.items() if k in repos}

    cmd = repo_options[op]["cmd"]

    if len(exist_repos) == 1:
        for _, prop in exist_repos.items():
            run_cmd(cmd, prop["path"])
    else:
        errors = exec_async_tasks(
            async_run_cmd(cmd, cwd=prop["path"]) for name, prop in exist_repos.items()
        )

        for path in errors:
            if path:
                print(render_str(f"`{op} failed, path: {path}`<tomato>"))
