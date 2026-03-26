# -*- coding:utf-8 -*-

import json
import logging
import os
import pprint
from collections import Counter
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

from pigit.ext.executor import WAITING, REPLY, DECODE, Executor
from pigit.interactive.list_picker import PickerRow
from pigit.interactive.repo_cd import EMPTY_MANAGED_REPOS_MSG, run_repo_cd_picker


def iter_managed_repo_names(repos: Dict[str, dict]) -> List[str]:
    """Return managed repo names sorted by Unicode code points (stable across platforms)."""

    return sorted(repos.keys())


class ManagedRepos:
    """Persisted multi-repo registry (`repos.json`) and bulk commands."""

    @staticmethod
    def _repo_parallel_workers() -> int:
        """Max concurrent subprocesses for multi-repo commands.

        Override with env ``PIGIT_REPO_MAX_WORKERS`` (integer, clamped to 1..32).
        Default ``4`` keeps load predictable; see ``docs/optimization.md``.
        """
        raw = os.environ.get("PIGIT_REPO_MAX_WORKERS", "").strip()
        if raw.isdigit():
            return max(1, min(int(raw), 32))
        return 4

    def __init__(
        self,
        executor: Executor,
        repo_json_path: Optional[str] = None,
        log: Optional[logging.Logger] = None,
    ) -> None:
        self.executor = executor
        self.log = log
        self.repo_json_path = (
            Path("./repos.json") if repo_json_path is None else Path(repo_json_path)
        )
        self.repo_json_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _make_repo_name(path: str, repos: Dict[str, str], name_counts: Counter) -> str:
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

        name: str = os.path.basename(os.path.normpath(path))
        if name in repos or name_counts[name] > 1:
            # path has no trailing /
            par_name = os.path.basename(os.path.dirname(path))
            return os.path.join(par_name, name)
        return name

    def load_repos(self) -> Dict:
        """Load repos info from cache file."""

        if not self.repo_json_path.is_file():
            return {}

        with self.repo_json_path.open(mode="r") as fp:
            return json.load(fp)

    def dump_repos(self, repos: Dict) -> bool:
        """Dump repos info to cache file, re-write mode."""

        try:
            with self.repo_json_path.open(mode="w+") as fp:
                json.dump(repos, fp, indent=2)
                return True
        except Exception as e:
            self.log.error(f"Failed to dump repos: {e}")
            return False

    def clear_repos(self) -> None:
        self.repo_json_path.unlink(missing_ok=True)

    def report_repos(self, author: str, since: str, until: str) -> str:
        """Generate report of repos.

        range e.g.:
            git log --since="2023-01-01"  --until="2023-12-31"
            git log --since="1 month ago" --until="1 day ago"
            git log --since="1672531200"  --until="1675212800"
        """
        exist_repos = self.load_repos()
        if len(exist_repos) == 0:
            return "No repo(s) managed."

        command = f"git log --color=never --oneline"
        if author != "":
            command += f' --author="{author}"'
        if since != "":
            command += f' --since="{since}"'
        if until != "":
            command += f' --until="{until}"'
        if since == "" and until == "":
            command += " -30"

        items = list(exist_repos.items())
        workers = self._repo_parallel_workers()
        orders = [{"cwd": prop["path"]} for _, prop in items]
        cmds = [command] * len(items)
        results = self.executor.exec_parallel(
            *cmds,
            orders=orders,
            flags=REPLY | DECODE,
            max_concurrent=workers,
        )

        report_dict = {}
        for (repo_name, _prop), (_code, _err, resp) in zip(items, results):
            commits = []
            for line in (resp or "").split("\n"):
                if line == "":
                    continue

                line = line.split(" ", maxsplit=1)[1]
                if line.startswith("Merge branch"):
                    continue

                commits.append(line)

            report_dict[repo_name] = commits
        pprint.pprint(report_dict)

    def ll_repos(self, reverse: bool = False) -> Generator[List[Tuple], None, None]:
        exist_repos = self.load_repos()

        for repo_name in iter_managed_repo_names(exist_repos):
            prop = exist_repos[repo_name]
            repo_path = prop["path"]
            head = self.get_head(repo_path)

            # jump invalid repo.
            if head is None:
                if reverse:
                    yield [
                        (repo_name, ""),
                        ("Local Path", repo_path),
                    ]

            elif not reverse:
                _, _, unstaged = self.executor.exec(
                    "git diff --stat", flags=REPLY | DECODE, cwd=repo_path
                )
                _, _, staged = self.executor.exec(
                    "git diff --stat --cached", flags=REPLY | DECODE, cwd=repo_path
                )
                _, _, untracked = self.executor.exec(
                    "git ls-files -zo --exclude-standard",
                    flags=REPLY | DECODE,
                    cwd=repo_path,
                )
                commit_hash = self.get_first_pushed_commit(
                    path=repo_path, branch_name=head
                )
                commit = self.load_log(
                    limit=1,
                    arg_str="--format='%s (%cd)||%C(auto)%d%n' --date=relative --color",
                    path=repo_path,
                )

                commit_msg, branch_status = commit.strip().split("||")
                unstaged_symbol = "*" if unstaged else " "
                staged_symbol = "+" if staged else " "
                untracked_symbol = "?" if untracked else " "

                yield [
                    (repo_name, ""),
                    (
                        "Branch",
                        f"{head} {unstaged_symbol}{staged_symbol}{untracked_symbol}",
                    ),
                    ("Status", branch_status),
                    ("Commit Hash", commit_hash),
                    ("Commit Msg", commit_msg),
                    ("Local Path", repo_path),
                ]

    def add_repos(self, paths: List[str], dry_run: bool = False) -> List:
        """Traverse the incoming paths. If it is not saved and is a git
        directory, add it to repos.

        Args:
            paths (list[str]): incoming paths.
            dry_run (bool, optional): Show but not really execute. Defaults to False.
            silent (bool, optional): No output. Defaults to False.
        """

        exist_repos = self.load_repos()
        exist_paths_set = {r["path"] for r in exist_repos.values()}

        new_git_paths = []
        for path in paths:
            repo_path, _ = self.confirm_repo(path)
            if repo_path and repo_path not in exist_paths_set:
                new_git_paths.append(repo_path)

        if new_git_paths and not dry_run:
            name_counts = Counter(
                os.path.basename(os.path.normpath(p)) for p in new_git_paths
            )
            new_repos = {
                self._make_repo_name(path, exist_repos, name_counts): {"path": path}
                for path in new_git_paths
            }

            self.dump_repos({**exist_repos, **new_repos})

        return new_git_paths

    def rm_repos(self, repos: List[str], use_path: bool = False) -> List[Tuple]:
        exist_repos = self.load_repos()

        del_repos = []
        del_paths = []
        if use_path:
            del_repos.extend(
                repo for repo, info in exist_repos.items() if info["path"] in repos
            )
        else:
            del_repos.extend(repo for repo in repos if exist_repos.get(repo))

        for repo in del_repos:
            del_paths.append(exist_repos[repo]["path"])
            del exist_repos[repo]

        self.dump_repos(exist_repos)
        return list(zip(del_repos, del_paths))

    def rename_repo(self, repo: str, name: str) -> Tuple[bool, str]:
        """Rename repo

        Args:
            repo (str): exist repo name
            name (str): new name

        Returns:
            Tuple[bool, str]: whether rename successful, tip msg.
        """

        exist_repos = self.load_repos()

        if name == repo:
            return False, "The same name do nothing!"
        elif name in exist_repos:
            return False, f"'{name}' is already in use!"
        elif repo not in exist_repos:
            return False, f"'{repo}' is not a valid repo name!"
        else:
            prop = exist_repos[repo]
            del exist_repos[repo]
            exist_repos[name] = prop

            self.dump_repos(exist_repos)
            return True, f"rename successful, `{repo}`->`{name}`."

    def cd_repo(
        self,
        repo: Optional[str] = None,
        *,
        pick: bool = False,
        pick_alt_screen: bool = False,
    ) -> Tuple[int, Optional[str]]:
        """Quick jump to repo dir.

        Args:
            repo: Managed repo name, or ``None`` to choose interactively (legacy or ``--pick``).
            pick: If ``True``, use the built-in TTY picker when the name is missing or not
                an exact key (requires a terminal for the picker path).

        Returns:
            ``(exit_code, message)``. The handler maps non-zero codes to :exc:`SystemExit`.
        """

        command = "$SHELL -c 'cd {0} && exec $SHELL'"
        exist_repos = self.load_repos()

        if pick:
            if not exist_repos:
                return 1, EMPTY_MANAGED_REPOS_MSG
            if repo is not None and repo in exist_repos:
                path = exist_repos[repo]["path"]
                self.executor.exec(command.format(path), flags=WAITING)
                return 0, None
            rows = [
                PickerRow(
                    title=name,
                    # detail=exist_repos[name]["path"],
                    ref=exist_repos[name]["path"],
                )
                for name in iter_managed_repo_names(exist_repos)
            ]
            initial_filter = "" if repo is None else repo
            return run_repo_cd_picker(
                rows,
                self.executor,
                initial_filter=initial_filter,
                pick_alt_screen=pick_alt_screen,
            )

        if repo is not None and repo in exist_repos:
            path = exist_repos[repo]["path"]
            self.executor.exec(command.format(path), flags=WAITING)
            return 0, None

        cur_cache = iter_managed_repo_names(exist_repos)
        print("Managed repos include the following:")
        for i, r in enumerate(cur_cache):
            print(".  ", i, r)

        try:
            input_num = int(input("Please input the index:"))
            if 0 <= input_num < len(cur_cache):
                path = exist_repos[cur_cache[input_num]]["path"]
                print(self.executor.exec(command.format(path), cwd=".", flags=WAITING))
            else:
                print("Error: index out of range.")
        except Exception:
            print("Error: index need input a number.")
        return 0, None

    def process_repos_option(self, repos: Optional[List[str]], cmd: str):
        exist_repos = self.load_repos()
        print(f":: {cmd}\n")

        if repos:
            exist_repos = {k: v for k, v in exist_repos.items() if k in repos}

        if len(exist_repos) >= 1:
            cmds = []
            orders = []
            for _, prop in exist_repos.items():
                cmds.append(cmd)
                orders.append({"cwd": prop["path"]})

            return self.executor.exec_parallel(
                *cmds,
                orders=orders,
                flags=WAITING,
                max_concurrent=self._repo_parallel_workers(),
            )

        for _, prop in exist_repos.items():
            self.executor.exec(cmd, flags=WAITING, cwd=prop["path"])
