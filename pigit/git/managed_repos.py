from __future__ import annotations

import json
import logging
import os
import pprint
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collections.abc import Generator

from pigit.ext.executor import WAITING, REPLY, DECODE, Executor
from pigit.git.repo_cd_picker import EMPTY_MANAGED_REPOS_MSG, run_repo_cd_picker
from pigit.picker_app import PickerRow

_logger = logging.getLogger(__name__)


def iter_managed_repo_names(repos: dict[str, dict]) -> list[str]:
    """Return managed repo names sorted by Unicode code points (stable across platforms)."""

    return sorted(repos.keys())


def _write_path_or_return(path: str, output_file: str | None) -> tuple[int, str | None]:
    """Write ``path`` to ``output_file`` when given, otherwise return it."""
    if output_file is not None:
        with open(output_file, "w") as f:
            f.write(path)
        return 0, None
    return 0, path


def _fuzzy_match(text: str, query: str) -> bool:
    """Check if all characters of `query` appear in `text` in order (case-insensitive)."""
    if not query:
        return True
    text = text.lower()
    query = query.lower()
    idx = 0
    for ch in query:
        idx = text.find(ch, idx)
        if idx == -1:
            return False
        idx += 1
    return True


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
        repo_json_path: str | None = None,
    ) -> None:
        self.executor = executor
        self.repo_json_path = (
            Path("./repos.json") if repo_json_path is None else Path(repo_json_path)
        )
        self.repo_json_path.parent.mkdir(parents=True, exist_ok=True)
        self._local_git = None

    @property
    def _git(self):
        if self._local_git is None:
            from .local_git import LocalGit

            self._local_git = LocalGit(executor=self.executor)
        return self._local_git

    @staticmethod
    def _make_repo_name(path: str, repos: dict[str, dict], name_counts: Counter) -> str:
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

    def load_repos(self) -> dict[str, dict]:
        """Load repos info from cache file."""

        try:
            with self.repo_json_path.open(mode="r") as fp:
                return json.load(fp)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def dump_repos(self, repos: dict) -> bool:
        """Dump repos info to cache file, re-write mode."""

        try:
            with self.repo_json_path.open(mode="w") as fp:
                json.dump(repos, fp, indent=2)
                return True
        except (OSError, TypeError) as e:
            _logger.error("Failed to dump repos: %s", e)
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
        for (repo_name, _prop), (_code, _err, resp) in zip(items, results, strict=True):
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
        return ""

    @staticmethod
    def _format_repo_row(repo_name: str, repo_path: str, meta: dict) -> list[tuple]:
        symbols = (
            f"{'*' if meta.get('dirty') else ' '}"
            f"{'+' if meta.get('staged') else ' '}"
            f"{'?' if meta.get('untracked') else ' '}"
        )
        return [
            (repo_name, ""),
            ("Branch", f"{meta.get('branch', '')} {symbols}"),
            ("Status", meta.get("status", "")),
            ("Commit Hash", meta.get("commit_hash", "")),
            ("Commit Msg", meta.get("commit_msg", "")),
            ("Author", meta.get("commit_author", "")),
            ("Local Path", repo_path),
        ]

    def ll_repos(
        self, reverse: bool = False, filter_query: str = ""
    ) -> Generator[list[tuple], None, None]:
        exist_repos = self.load_repos()

        for repo_name in iter_managed_repo_names(exist_repos):
            if filter_query and not _fuzzy_match(repo_name, filter_query):
                continue
            prop = exist_repos[repo_name]
            repo_path = prop["path"]
            meta = prop.get("meta")

            if meta and self._is_meta_fresh(repo_path, meta):
                yield self._format_repo_row(repo_name, repo_path, meta)
                continue

            head = self._git.get_head(repo_path)

            # jump invalid repo.
            if head is None:
                if reverse:
                    yield [
                        (repo_name, ""),
                        ("Local Path", repo_path),
                    ]
                continue

            if not reverse:
                meta = self._fetch_repo_meta(repo_path)
                if meta:
                    yield self._format_repo_row(repo_name, repo_path, meta)

    def add_repos(self, paths: list[str], dry_run: bool = False) -> list:
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
            repo_path, _ = self._git.confirm_repo(path)
            if repo_path and repo_path not in exist_paths_set:
                new_git_paths.append(repo_path)

        if dry_run:
            return new_git_paths

        if not new_git_paths:
            return []

        name_counts = Counter(
            os.path.basename(os.path.normpath(p)) for p in new_git_paths
        )
        for path in new_git_paths:
            name = self._make_repo_name(path, exist_repos, name_counts)
            exist_repos[name] = {"path": path}
            new_meta = self._fetch_repo_meta(path)
            if new_meta:
                exist_repos[name]["meta"] = new_meta

        self.dump_repos(exist_repos)
        return new_git_paths

    def refresh_meta(
        self,
        names: list[str] | None = None,
        *,
        force: bool = False,
    ) -> Generator[str, None, None]:
        """Refresh cached metadata for managed repos, yielding each refreshed name.

        Args:
            names: Repo names to refresh. If None, refresh all managed repos.
            force: When True, always re-fetch metadata regardless of cache freshness.

        Yields:
            Repo name whose metadata was successfully refreshed.
        """
        exist_repos = self.load_repos()
        if not exist_repos:
            return

        targets = {
            name: info
            for name, info in exist_repos.items()
            if names is None or name in names
        }
        if not targets:
            return

        # Pre-filter skipped repos (cache fresh and not forced).
        to_refresh: dict[str, str] = {}
        for name, info in targets.items():
            repo_path = info.get("path")
            if not repo_path:
                continue
            if not force:
                meta = info.get("meta")
                if meta and self._is_meta_fresh(repo_path, meta):
                    continue
            to_refresh[name] = repo_path

        if not to_refresh:
            return

        def _fetch_one(item: tuple[str, str]) -> tuple[str, dict | None]:
            name, repo_path = item
            return name, self._fetch_repo_meta(repo_path)

        refreshed: list[str] = []
        try:
            with ThreadPoolExecutor(max_workers=self._repo_parallel_workers()) as pool:
                futures = {
                    pool.submit(_fetch_one, item): item[0]
                    for item in to_refresh.items()
                }
                for future in as_completed(futures):
                    name, new_meta = future.result()
                    if new_meta:
                        exist_repos[name]["meta"] = new_meta
                        refreshed.append(name)
                        yield name
        finally:
            if refreshed:
                self.dump_repos(exist_repos)

    def rm_repos(self, repos: list[str], use_path: bool = False) -> list[tuple]:
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
        return list(zip(del_repos, del_paths, strict=True))

    def rename_repo(self, repo: str, name: str) -> tuple[bool, str]:
        """Rename repo

        Args:
            repo (str): exist repo name
            name (str): new name

        Returns:
            tuple[bool, str]: whether rename successful, tip msg.
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
        repo: str | None = None,
        *,
        pick: bool = False,
        output_file: str | None = None,
    ) -> tuple[int, str | None]:
        """Resolve managed repo path, optionally via interactive picker.

        Args:
            repo: Managed repo name, or ``None`` to choose interactively.
            pick: If ``True``, use the TTY picker when the name is missing or not
                an exact key (requires a terminal for the picker path).
            output_file: When provided, write the resolved path to this file
                instead of returning it.

        Returns:
            ``(exit_code, path | None)``. ``0`` with the resolved path,
            or ``None`` when written to ``output_file``.
        """

        exist_repos = self.load_repos()

        if pick:
            if not exist_repos:
                return 1, EMPTY_MANAGED_REPOS_MSG
            if repo is not None and repo in exist_repos:
                return _write_path_or_return(exist_repos[repo]["path"], output_file)
            rows = [
                PickerRow(
                    title=name,
                    ref=exist_repos[name]["path"],
                )
                for name in iter_managed_repo_names(exist_repos)
            ]
            initial_filter = "" if repo is None else repo
            exit_code, result = run_repo_cd_picker(
                rows,
                initial_filter=initial_filter,
            )
            if exit_code == 0 and result is not None:
                return _write_path_or_return(result, output_file)
            return exit_code, result

        if repo is not None and repo in exist_repos:
            return _write_path_or_return(exist_repos[repo]["path"], output_file)

        cur_cache = iter_managed_repo_names(exist_repos)
        print("Managed repos include the following:")
        for i, r in enumerate(cur_cache):
            print(".  ", i, r)

        try:
            input_num = int(input("Please input the index:"))
            if 0 <= input_num < len(cur_cache):
                return _write_path_or_return(
                    exist_repos[cur_cache[input_num]]["path"], output_file
                )
            else:
                print("Error: index out of range.")
        except Exception:
            print("Error: index need input a number.")
        return 0, None

    def process_repos_option(self, repos: list[str] | None, cmd: str):
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

    def branch_new_repos(
        self,
        branch_name: str,
        repos: list[str] | None = None,
        *,
        checkout: bool = False,
        base: str | None = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> tuple[bool, list[tuple[str, str]], list[tuple[str, int, str | None]]]:
        """Batch create new branches across managed repos.

        Returns:
            (all_ok, blockers, results)
            - all_ok: bool, whether pre-flight passed and execution succeeded.
            - blockers: list of (repo_name, reason) from pre-flight failures.
            - results: list of (repo_name, exit_code, stderr_or_none) from execution.
              Empty if pre-flight failed or dry_run.
        """
        exist_repos = self.load_repos()
        if repos:
            target_repos = {k: v for k, v in exist_repos.items() if k in repos}
        else:
            target_repos = exist_repos

        if not target_repos:
            return True, [], []

        blockers = self._branch_new_preflight(
            target_repos, branch_name, checkout=checkout, base=base, force=force
        )
        if blockers:
            return False, blockers, []

        if dry_run:
            return True, [], []

        results = self._branch_new_execute(
            target_repos, branch_name, checkout=checkout, base=base, force=force
        )
        return True, [], results

    def _branch_new_preflight(
        self,
        target_repos: dict[str, dict],
        branch_name: str,
        *,
        checkout: bool,
        base: str | None,
        force: bool,
    ) -> list[tuple[str, str]]:
        """Run three-phase pre-flight checks in parallel."""
        blockers: list[tuple[str, str]] = []
        repo_items = list(target_repos.items())

        # 1. validity check
        validity_cmds = ["git rev-parse --git-dir"] * len(repo_items)
        validity_orders = [{"cwd": prop["path"]} for _, prop in repo_items]
        validity_results = self.executor.exec_parallel(
            *validity_cmds,
            orders=validity_orders,
            flags=REPLY | DECODE,
            max_concurrent=self._repo_parallel_workers(),
        )

        valid_repos: dict[str, dict] = {}
        for (name, prop), (code, _err, _out) in zip(
            repo_items, validity_results, strict=True
        ):
            if code != 0:
                blockers.append((name, "invalid repo"))
            else:
                valid_repos[name] = prop

        if not valid_repos:
            return blockers

        # 2. branch existence check
        branch_cmds = [f"git branch --list {branch_name}"] * len(valid_repos)
        branch_orders = [{"cwd": prop["path"]} for prop in valid_repos.values()]
        branch_results = self.executor.exec_parallel(
            *branch_cmds,
            orders=branch_orders,
            flags=REPLY | DECODE,
            max_concurrent=self._repo_parallel_workers(),
        )

        clean_repos: dict[str, dict] = {}
        for (name, prop), (code, _err, out) in zip(
            valid_repos.items(), branch_results, strict=True
        ):
            if out and out.strip():
                if not force:
                    blockers.append((name, f"branch '{branch_name}' already exists"))
                    continue
            clean_repos[name] = prop

        if not clean_repos:
            return blockers

        # 3. workspace cleanliness check (only when checkout or base)
        if checkout or base:
            status_cmds = ["git status --porcelain"] * len(clean_repos)
            status_orders = [{"cwd": prop["path"]} for prop in clean_repos.values()]
            status_results = self.executor.exec_parallel(
                *status_cmds,
                orders=status_orders,
                flags=REPLY | DECODE,
                max_concurrent=self._repo_parallel_workers(),
            )

            for (name, prop), (code, _err, out) in zip(
                clean_repos.items(), status_results, strict=True
            ):
                if out and out.strip():
                    blockers.append((name, "uncommitted changes"))

        return blockers

    def _branch_new_execute(
        self,
        target_repos: dict[str, dict],
        branch_name: str,
        *,
        checkout: bool,
        base: str | None,
        force: bool,
    ) -> list[tuple[str, int, str | None]]:
        """Execute branch creation across repos in parallel."""
        parts: list[str] = []
        if base:
            parts.append(f"git checkout {base}")
        if checkout:
            parts.append(f"git checkout -b {branch_name}")
        else:
            flag = " -f" if force else ""
            parts.append(f"git branch{flag} {branch_name}")
        cmd = " && ".join(parts)

        repo_items = list(target_repos.items())
        cmds = [cmd] * len(repo_items)
        orders = [{"cwd": prop["path"]} for _, prop in repo_items]
        results = self.executor.exec_parallel(
            *cmds,
            orders=orders,
            flags=REPLY | DECODE,
            max_concurrent=self._repo_parallel_workers(),
        )

        return [
            (name, code, stderr if code != 0 else None)
            for (name, _), (code, stderr, _stdout) in zip(
                repo_items, results, strict=True
            )
        ]

    # --- Metadata caching helpers ---

    def _resolve_git_dir(self, repo_path: str) -> str:
        try:
            return self._git.get_git_dir(repo_path)
        except Exception:
            return os.path.join(repo_path, ".git")

    def _is_meta_fresh(self, repo_path: str, meta: dict) -> bool:
        """Check whether cached metadata is still valid by comparing .git/index mtime."""
        cached_mtime = meta.get("index_mtime")
        if not isinstance(cached_mtime, int):
            return False
        git_dir = self._resolve_git_dir(repo_path)
        index_path = os.path.join(git_dir, "index")
        try:
            return int(os.path.getmtime(index_path)) == cached_mtime
        except OSError:
            return False

    def _fetch_repo_meta(self, repo_path: str) -> dict | None:
        """Fetch git metadata for a single repo and return a cacheable dict."""
        head = self._git.get_head(repo_path)
        if not head:
            return None

        _, _, status_out = self.executor.exec(
            "git status --porcelain", flags=REPLY | DECODE, cwd=repo_path
        )
        has_unstaged = False
        has_staged = False
        has_untracked = False
        status_text = status_out if isinstance(status_out, str) else ""
        for line in status_text.splitlines():
            if not line:
                continue
            xy = line[:2]
            if "?" in xy:
                has_untracked = True
                continue
            if xy[0] != " ":
                has_staged = True
            if xy[1] != " ":
                has_unstaged = True

        commit_hash = self._git.get_first_pushed_commit(
            path=repo_path, branch_name=head
        )
        commit = self._git.load_log(
            limit=1,
            arg_str="--format='%s (%cd)||%at||%d||%an||%ae%n' --date=relative --color",
            path=repo_path,
        )

        commit_msg, commit_time, branch_status = "", 0, ""
        author_name, author_email = "", ""
        if "||" in commit:
            parts = commit.strip().split("||", 4)
            commit_msg = parts[0]
            commit_time = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            branch_status = parts[2] if len(parts) > 2 else ""
            author_name = parts[3] if len(parts) > 3 else ""
            author_email = parts[4] if len(parts) > 4 else ""
        else:
            commit_msg = commit.strip()

        ahead, behind = "?", "?"
        for branch in self._git.load_branches(path=repo_path, scope="local"):
            if branch.is_head:
                ahead = branch.ahead
                behind = branch.behind
                break

        git_dir = self._resolve_git_dir(repo_path)
        try:
            index_mtime = int(os.path.getmtime(os.path.join(git_dir, "index")))
        except OSError:
            index_mtime = 0

        return {
            "branch": head,
            "status": branch_status,
            "commit_hash": commit_hash,
            "commit_msg": commit_msg,
            "commit_time": commit_time,
            "commit_author": author_name,
            "commit_author_email": author_email,
            "ahead": ahead,
            "behind": behind,
            "dirty": bool(has_unstaged or has_staged or has_untracked),
            "staged": bool(has_staged),
            "untracked": bool(has_untracked),
            "index_mtime": index_mtime,
        }
