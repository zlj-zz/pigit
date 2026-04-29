# -*- coding:utf-8 -*-

import logging
import re
import shlex
import time
import shutil
import textwrap
from pathlib import Path
from typing import Iterator, Optional, Union

from plenty.str_utils import shorten, byte_str2str
from plenty.console import Console

from pigit.ext.executor import SILENT, WAITING, REPLY, DECODE, Executor
from pigit.ext.utils import adjudgment_type, get_file_icon
from .model import File, Commit, Branch


class RepoError(Exception):
    """Error class of ~GitOption."""


class GitError(Exception):
    """Raised when a git command fails."""


def _file_path_for_cmd(file: Union[File, str]) -> str:
    if isinstance(file, File):
        return file.get_file_str()
    s = str(file)
    return s.split("->")[-1].strip() if "->" in s else s


class LocalGit:
    """Single working-copy git operations (optional default `path`)."""

    _RE_CONFIG_NEWLINE = re.compile(r"\r\n|\r|\n")
    _RE_CONFIG_URL = re.compile(r"url\s=\s(.*)")
    _RE_BRANCH_AHEAD = re.compile(r"ahead (\d+)")
    _RE_BRANCH_BEHIND = re.compile(r"behind (\d+)")
    _RE_COMMIT_TAG = re.compile(r"tag: ([^,\\]+)")
    _LOAD_STATUS_CACHE_TTL = 0.3

    def __init__(
        self,
        executor: Executor,
        path: Optional[str] = None,
        log: Optional[logging.Logger] = None,
    ) -> None:
        self.executor = executor
        self.log = log
        self.path = path

    def confirm_repo(
        self, given_path: Optional[str] = None, exclude_submodule: bool = False
    ) -> tuple[str, str]:
        """Confirm given path whether a git repo. And return repo path info.
        Get the current git repository path. If not, the path is empty.
        Get the local git config path. If not, the path is empty.

        Uses ``git rev-parse --show-toplevel`` so the work tree root is absolute
        even when ``given_path`` is a subdirectory (e.g. TUI started under ``pkg/``).

        Args:
            exclude_submodule: Reserved for API compatibility; unused.
        """
        _ = exclude_submodule
        path = given_path if given_path is not None else self.path
        if path is None or path == "":
            path = "."
        path = str(Path(path).resolve())

        repo_path: str = ""
        git_conf_path: str = ""

        if not Path(path).is_dir():
            return repo_path, git_conf_path

        code, _err, top_out = self.executor.exec(
            "git rev-parse --show-toplevel",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if code is None or code != 0 or not top_out or not str(top_out).strip():
            return "", ""

        repo_path = str(Path(str(top_out).strip()).resolve())

        code2, _err2, gd_out = self.executor.exec(
            "git rev-parse --git-dir",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if code2 is None or code2 != 0 or not gd_out or not str(gd_out).strip():
            return "", ""

        git_dir_raw = str(gd_out).strip()
        if Path(git_dir_raw).is_absolute():
            git_conf_path = str(Path(git_dir_raw).resolve())
        else:
            git_conf_path = str((Path(repo_path) / git_dir_raw).resolve())

        return repo_path, git_conf_path

    def get_config(self, path: Optional[str] = None) -> dict[str, dict[str, str]]:
        """Try to read git config and parse, return a config dict.

        Args:
            path (Optional[str], optional): repo path. Defaults to None.

        Returns:
            dict[str, dict[str, str]]: config dict.
        """
        path = path or self.path

        _, config_path = self.confirm_repo(path)
        try:
            with open(Path(config_path) / "config", "r") as cf:
                context = cf.read()
        except Exception as e:
            self.log.warning(f"Can not read config with: {e}")
            return {}
        else:
            conf_dict: dict[str, dict[str, str]] = {}
            conf_list = re.split(self._RE_CONFIG_NEWLINE, context)
            config_type: str = ""

            for line in conf_list:
                line = line.strip()

                if not line:
                    continue

                elif line.startswith("["):
                    config_type = line[1:-1].strip()
                    conf_dict[config_type] = {}

                elif "=" in line:
                    key, value = line.split("=", 1)
                    conf_dict[config_type][key.strip()] = value.strip()

                else:
                    continue

            return conf_dict

    def get_head(self, path: Optional[str] = None) -> Optional[str]:
        """Get current repo head. Return a branch name or a commit sha string."""
        path = path or self.path

        _, _, head = self.executor.exec(
            "git symbolic-ref -q --short HEAD || git describe --tags --exact-match",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if head is not None:
            head = head.rstrip()
        return head

    def get_first_pushed_commit(
        self, path: Optional[str] = None, branch_name: Optional[str] = None
    ) -> str:
        path = path or self.path

        if branch_name is None:
            if head := self.get_head(path):
                branch_name = head
            else:
                return ""

        command = "git merge-base %s %s@{u}" % (
            shlex.quote(branch_name),
            shlex.quote(branch_name),
        )
        _, _, commit_msg = self.executor.exec(command, flags=REPLY | DECODE, cwd=path)
        return commit_msg.strip()

    def get_branches(
        self,
        path: Optional[str] = None,
        include_remote: bool = False,
        plain: bool = True,
    ) -> list[str]:
        """Get repo all branch."""
        path = path or self.path

        include_all = "--all" if include_remote else ""
        color = "never" if plain else "always"

        _, _, res = self.executor.exec(
            f"git branch {include_all} --color={color}",
            flags=REPLY | DECODE,
            cwd=path,
        )

        if res is None:
            return []
        return [branch[2:] for branch in res.rstrip().split("\n")]

    def get_remotes(self, path: Optional[str] = None) -> list[str]:
        """Get repo remote url."""

        # Get remote name, exit when error.
        path = path or self.path
        _, _, res = self.executor.exec(
            "git remote show", flags=REPLY | DECODE, cwd=path
        )

        return res.strip().split("\n") if res else []

    def get_remote_url(
        self, path: Optional[str] = None, remote_name: Optional[str] = None
    ) -> str:
        """Get repo remote url."""
        path = path or self.path

        if remote_name is None:
            if remotes := self.get_remotes(path):
                remote_name = remotes[0]
            else:
                return ""

        # Get remote url, exit when error.
        _, err, remote_url = self.executor.exec(
            f"git ls-remote --get-url {shlex.quote(remote_name)}",
            flags=REPLY | DECODE,
            cwd=path,
        )

        if err:
            return ""

        remote_url = remote_url[:-5]
        return remote_url

    def get_summary(self, path: Optional[str] = None, plain: bool = True) -> str:
        path = path or self.path
        color = "never" if plain else "always"
        _, _, summary = self.executor.exec(
            f"git shortlog --summary --numbered --color={color}",
            flags=REPLY | DECODE,
            cwd=path,
        )
        return summary

    def get_repo_desc(
        self,
        include_part: Optional[list] = None,
        path: Optional[str] = None,
        color: bool = True,
    ) -> str:
        """Return a string of repo various information.

        Args:
                include_part (Optional[list], optional): should return info part: [path,remote,branch,log,summary]. Defaults to None.
                path (Optional[str], optional): custom repo path. Defaults to None.
                color (bool, optional): whether return with color. Defaults to True.

        Returns:
                str: desc info.
        """
        path = path or self.path
        error_str = "`Error getting.`<error>"
        gen = ["[b`Repository Information`]" if color else "[Repository Information]"]
        repo_path, _ = self.confirm_repo(path)

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
                with open(Path(repo_path) / ".git" / "config", "r") as cf:
                    config = cf.read()
            except Exception:
                remote = error_str
            else:
                res = re.findall(self._RE_CONFIG_URL, config)
                remote = "\n".join(
                    [f"\ti`{x}`<sky_blue>" if color else f"\t{x}" for x in res]
                )
            gen.append("Remote: \n%s\n" % remote)

        # Get all branches.
        if not include_part or "branch" in include_part:
            branches = self.get_branches(path, include_remote=True, plain=not color)
            branches_str = (
                "\n".join(f"\t{branch}" for branch in branches)
                if branches
                else f"\t{error_str}"
            )
            gen.append("Branches: \n%s\n" % branches_str)

        # Get the latest log.
        if not include_part or "log" in include_part:
            _, err, res = self.executor.exec(
                f"git log --stat --oneline --decorate -1 --color={'always' if color else 'never'}",
                flags=REPLY | DECODE,
                cwd=path,
            )
            git_log = "\t" + error_str if err else textwrap.indent(res, "\t")
            gen.append("Latest log:\n%s\n" % git_log)

        # FIXME: will broken in a init repo.
        # Get git summary.
        # if not include_part or "summary" in include_part:
        #     summary = self.get_summary(path, not color)
        #     gen.append("Summary:\n%s\n" % summary or error_str)

        return "\n".join(gen)

    # =============
    # Special info
    # =============
    def load_branches(
        self,
        path: Optional[str] = None,
        *,
        scope: str = "local",
    ) -> list[Branch]:
        path = path or self.path
        branches: list[Branch] = []

        if scope == "remote":
            flag = "-r"
        elif scope == "all":
            flag = "-a"
        else:
            flag = ""

        _, _, resp = self.executor.exec(
            f"git branch {flag} --sort=-committerdate "
            '--format="%(HEAD)|%(refname:short)|%(refname)|%(upstream:short)|%(upstream:track)" ',
            flags=REPLY | DECODE,
            cwd=path,
        )
        resp = resp.strip()
        if not resp:
            return branches

        lines = resp.split("\n")

        for line in lines:
            items = line.split("|")
            short_name = items[1]
            full_ref = items[2]
            is_remote = full_ref.startswith("refs/remotes/")

            # Skip the symbolic HEAD ref for remotes (e.g. origin/HEAD)
            if is_remote and short_name.endswith("/HEAD"):
                continue

            branch = Branch(
                name=short_name,
                ahead="?",
                behind="?",
                is_head=items[0] == "*" and not is_remote,
                is_remote=is_remote,
            )

            upstream_name = items[3]

            if not upstream_name or is_remote:
                branches.append(branch)
                continue

            branch.upstream_name = upstream_name

            track = items[4]
            branch.ahead = (
                str(m[1]) if (m := self._RE_BRANCH_AHEAD.search(track)) else "0"
            )
            branch.behind = (
                str(m[1]) if (m := self._RE_BRANCH_BEHIND.search(track)) else "0"
            )
            branches.append(branch)

        return branches

    def load_log(
        self,
        branch_name: str = "",
        limit: Optional[int] = None,
        filter_path: str = "",
        arg_str: str = '--oneline --pretty=format:"%H|%at|%aN|%d|%p|%s" --abbrev=20 --date=unix',
        path: Optional[str] = None,
    ) -> str:
        path = path or self.path

        limit_flag = f"-{limit}" if limit else ""
        filter_flag = f"--follow -- {filter_path}" if filter_path else ""

        branch_part = shlex.quote(branch_name) if branch_name else ""
        limit_part = f"-{limit}" if limit else ""
        filter_part = f"--follow -- {shlex.quote(filter_path)}" if filter_path else ""
        _, _, resp = self.executor.exec(
            f"git log {branch_part} {arg_str} {limit_part} {filter_part}",
            flags=REPLY | DECODE,
            cwd=path,
        )

        return "" if resp is None else resp.strip()

    @staticmethod
    def _find_dot_git_dir(cwd: str) -> Optional[str]:
        cur = Path(cwd).resolve()
        while True:
            git = cur / ".git"
            if git.is_dir():
                return str(git)
            if git.is_file():
                return None
            parent = cur.parent
            if parent == cur:
                return None
            cur = parent

    def _load_status_cache_signature(
        self, cwd: str
    ) -> Optional[tuple[int, int, int, int, bool]]:
        git_dir = self._find_dot_git_dir(cwd)
        if not git_dir:
            return None

        def st(p: "Path") -> tuple[int, int]:
            try:
                s = p.stat()
                return (s.st_mtime_ns, s.st_size)
            except OSError:
                return (0, 0)

        git = Path(git_dir)
        index_p = git / "index"
        head_p = git / "HEAD"
        merge = git / "MERGE_HEAD"
        i0, i1 = st(index_p)
        h0, h1 = st(head_p)
        return (i0, i1, h0, h1, merge.exists())

    def load_status(
        self,
        path: Optional[str] = None,
        use_cache: bool = True,
    ) -> list[File]:
        """Get the file tree status of GIT for processing and encapsulation.

        Returns structured ``File`` objects; formatting and truncation are the
        caller's responsibility (e.g. the panel layer).

        Args:
                use_cache (bool): When True, reuse recent result if git metadata unchanged
                    and within a short TTL (see class constant ``_LOAD_STATUS_CACHE_TTL``).

        Returns:
                (list[File]): Processed file status list.
        """
        path = path or self.path
        if path is None or path == "":
            workdir = str(Path(".").resolve())
        else:
            workdir = str(Path(path).resolve())

        key = (workdir,)
        now = time.monotonic()
        cache_sig = self._load_status_cache_signature(workdir) if use_cache else None

        if use_cache and cache_sig is not None:
            c = getattr(self, "_load_status_cache", None)
            if (
                c
                and c["key"] == key
                and c["sig"] == cache_sig
                and (now - c["time"] < self._LOAD_STATUS_CACHE_TTL)
            ):
                return c["files"]

        file_items = []

        _, err, files = self.executor.exec(
            "git status -s -u --porcelain", flags=REPLY | DECODE, cwd=workdir
        )
        if err:
            return file_items
        for file in files.rstrip().split("\n"):
            if not file.strip():
                # skip blank line.
                continue

            change = file[:2]
            staged_change = file[:1]
            unstaged_change = file[1:2]
            name = file[3:]
            if name.endswith('"'):
                # may is chinese char code.
                name = byte_str2str(name[1:-1])
            untracked = change in ["??", "A ", "AM"]
            has_no_staged_change = staged_change in [" ", "U", "?"]
            has_merged_conflicts = change in ["DD", "AA", "UU", "AU", "UA", "UD", "DU"]
            has_inline_merged_conflicts = change in ["UU", "AA"]

            file_ = File(
                name=name,
                display_str=name,
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

        if use_cache and cache_sig is not None:
            self._load_status_cache = {
                "key": key,
                "sig": cache_sig,
                "time": now,
                "files": file_items,
            }
        return file_items

    def load_file_diff(
        self,
        file: str,
        tracked: bool = True,
        cached: bool = False,
        plain: bool = False,
        path: Optional[str] = None,
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
        path = path or self.path

        _plain = "--color=never" if plain else "--color=always"
        _cached = "--cached" if cached else ""
        _tracked = "--" if tracked else "--no-index -- /dev/null"

        if "->" in file:  # rename status.
            file = file.split("->")[-1].strip()

        _, err, res = self.executor.exec(
            f"git diff --submodule --no-ext-diff {_plain} {_cached} {_tracked} "
            f"{shlex.quote(file)}",
            flags=REPLY | DECODE,
            cwd=path,
        )
        return "Can't get diff." if err else res.rstrip()

    def iter_commits(
        self,
        branch_name: str,
        limit: bool = True,
        max_commits: int = 300,
        filter_path: str = "",
        path: Optional[str] = None,
    ) -> Iterator[Commit]:
        """Yield commits for ``branch_name`` while reading ``git log`` as a stream.

        Args:
            branch_name: Branch ref to log.
            limit: When True, cap at ``max_commits`` (``git log -n``).
            max_commits: Max entries when ``limit`` is True.
            filter_path: Optional path filter (``--follow``).
            path: Repo root; defaults to :attr:`path`.
        """
        path = path or self.path

        first_pushed_commit = self.get_first_pushed_commit(path, branch_name)
        passed_first_pushed_commit = not first_pushed_commit

        branch_part = shlex.quote(branch_name) if branch_name else ""
        limit_part = f"-n {max_commits}" if limit else ""
        filter_part = f"--follow -- {shlex.quote(filter_path)}" if filter_path else ""
        command = (
            f"git log {branch_part} --oneline "
            f'--pretty=format:"%H|%at|%aN|%d|%P|%s" '
            f"{limit_part} --abbrev=20 --date=unix {filter_part}"
        ).strip()

        for line in self.executor.exec_stream(command, cwd=path):
            if not line.strip():
                continue
            split_ = line.split("|")
            if len(split_) < 6:
                continue

            sha = split_[0]
            unix_timestamp = int(split_[1])
            author = split_[2]
            extra_info = (split_[3]).strip()
            parent_str = split_[4].strip()
            message = "|".join(split_[5:])

            parents = parent_str.split() if parent_str else []

            tag = []
            if extra_info:
                if match := self._RE_COMMIT_TAG.search(extra_info):
                    tag.append(match[1])

            if sha == first_pushed_commit:
                passed_first_pushed_commit = True
            status = {True: "unpushed", False: "pushed"}[not passed_first_pushed_commit]

            yield Commit(
                sha=sha,
                msg=message,
                author=author,
                unix_timestamp=unix_timestamp,
                status=status,
                extra_info=extra_info,
                tag=tag,
                parents=parents,
            )

    def load_commits(
        self,
        branch_name: str,
        limit: bool = True,
        filter_path: str = "",
        path: Optional[str] = None,
        max_commits: int = 300,
    ) -> list[Commit]:
        """Get commits for a branch (materializes :meth:`iter_commits`)."""
        return list(
            self.iter_commits(
                branch_name,
                limit=limit,
                max_commits=max_commits,
                filter_path=filter_path,
                path=path,
            )
        )

    def load_commit_info(
        self,
        commit_sha: str = "",
        file_name: str = "",
        plain: bool = False,
        path: Optional[str] = None,
    ) -> str:
        """Gets the change of a file or all in a given commit.
        Args:
                commit_sha: commit id.
                file_name: file name(include full path).
                plain: whether has color.
        """
        path = path or self.path
        color_str = "never" if plain else "always"

        if file_name:
            cmd = f"git show --color={color_str} {shlex.quote(commit_sha)} -- {shlex.quote(file_name)}"
        else:
            cmd = f"git show --color={color_str} {shlex.quote(commit_sha)}"

        _, _, resp = self.executor.exec(
            cmd,
            flags=REPLY | DECODE,
            cwd=path,
        )
        return resp.rstrip()

    # ===============
    # Options of git
    # ===============
    def switch_file_status(self, file: File, path: Optional[str] = None):
        """Change the file stage status.

        Args:
            file (File): git file object.
            path (Optional[str], optional): exec path. Defaults to None.
        """
        path = path or self.path
        file_name = file.get_file_str()

        if file.has_merged_conflicts or file.has_inline_merged_conflicts:
            pass
        elif file.has_unstaged_change:
            self.executor.exec(
                f"git add -- {shlex.quote(file_name)}",
                flags=WAITING | SILENT,
                cwd=path,
            )
        elif file.has_staged_change:
            if file.tracked:
                self.executor.exec(
                    f"git reset HEAD -- {shlex.quote(file_name)}",
                    flags=WAITING | SILENT,
                    cwd=path,
                )
            else:
                self.executor.exec(
                    f"git rm --cached --force -- {shlex.quote(file_name)}",
                    flags=WAITING | SILENT,
                    cwd=path,
                )

    def discard_file(
        self,
        file: Union[File, str],
        path: Optional[str] = None,
        tracked: Optional[bool] = None,
    ):
        lookup = path if path is not None else self.path
        if lookup is None or lookup == "":
            lookup = "."
        lookup = str(Path(lookup).resolve())

        repo_root, _ = self.confirm_repo(lookup)
        if not repo_root:
            raise RepoError("Not a git repository.") from None

        file_name = _file_path_for_cmd(file)

        if tracked is None:
            if isinstance(file, File):
                tracked = file.tracked
            else:
                raise RepoError("Please set `tracked` or give a 'File'.") from None

        if tracked:
            code, err, out = self.executor.exec(
                f"git checkout -- {shlex.quote(file_name)}",
                flags=WAITING | REPLY | DECODE,
                cwd=repo_root,
            )
            if code is None:
                self.log.error(
                    "git checkout failed to run (executor error) path=%r cwd=%r",
                    file_name,
                    repo_root,
                )
            elif code != 0:
                detail = (err or out or "").strip() or "(no output)"
                self.log.error(
                    "git checkout failed (exit %s) path=%r cwd=%r: %s",
                    code,
                    file_name,
                    repo_root,
                    detail,
                )
        else:
            abs_file = (Path(repo_root) / file_name).resolve()
            try:
                if abs_file.is_dir() and not abs_file.is_symlink():
                    shutil.rmtree(abs_file)
                else:
                    abs_file.unlink()
            except FileNotFoundError:
                self.log.info("discard_file: skip missing untracked path %r", abs_file)
                return

    def ignore_file(self, file: Union[File, str], path: Optional[str] = None):
        """Append file to `.gitignore` file."""

        path = path or self.path
        repo_path, _ = self.confirm_repo(path)
        file_name = _file_path_for_cmd(file)

        with open(Path(repo_path) / ".gitignore", "a+") as f:
            f.write(f"\n{file_name}")

    def checkout_branch(self, branch_name: str, path: Optional[str] = None) -> None:
        path = path or self.path
        code, err, out = self.executor.exec(
            f"git checkout {shlex.quote(branch_name)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or f"checkout failed: {branch_name}")

    def get_file_info(
        self, file: Union[File, str], path: Optional[str] = None
    ) -> tuple[str, str]:
        """Get file size and last modification time as formatted strings.

        Returns:
            (size_str, mtime_str) like ("12.5K", "2026-04-24 10:30").
        """
        path = path or self.path
        file_name = _file_path_for_cmd(file)
        file_path = Path(path) / file_name
        try:
            st = file_path.stat()
            size = self._format_size(st.st_size)
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
            return size, mtime
        except OSError:
            return "?", "?"

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size}B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f}K"
        return f"{size / (1024 * 1024):.1f}M"

    def get_branch_recent_commit(
        self, branch_name: str, path: Optional[str] = None
    ) -> tuple[str, str]:
        """Get the most recent commit message and author for a branch."""
        path = path or self.path
        _, _, resp = self.executor.exec(
            f"git log {shlex.quote(branch_name)} -1 --pretty=format:%s|%aN",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if not resp:
            return "?", "?"
        parts = resp.split("|")
        return parts[0], parts[1] if len(parts) > 1 else "?"

    def get_branch_creation_time(
        self, branch_name: str, path: Optional[str] = None
    ) -> str:
        """Return branch creation date as YYYY-MM-DD (best-effort via reflog)."""
        path = path or self.path
        _, _, resp = self.executor.exec(
            f"git reflog show {shlex.quote(branch_name)} --format=%at | tail -1",
            flags=REPLY | DECODE,
            cwd=path,
            shell=True,
        )
        if not resp:
            return "?"
        try:
            ts = int(resp.strip())
            return time.strftime("%Y-%m-%d", time.localtime(ts))
        except ValueError:
            return "?"

    def get_commit_stats(
        self, commit_sha: str, path: Optional[str] = None
    ) -> tuple[list[tuple[str, int, int]], int, int]:
        """Get changed files and insertion/deletion counts for a commit.

        Returns:
            (files, total_insertions, total_deletions) where files is a list
            of (file_name, insertions, deletions).
        """
        path = path or self.path
        _, _, resp = self.executor.exec(
            f"git show --numstat --format= {shlex.quote(commit_sha)}",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if not resp:
            return [], 0, 0

        files: list[tuple[str, int, int]] = []
        total_add = 0
        total_del = 0

        for line in resp.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                add = int(parts[0]) if parts[0].isdigit() else 0
                delete = int(parts[1]) if parts[1].isdigit() else 0
                file_name = parts[2]
                files.append((file_name, add, delete))
                total_add += add
                total_del += delete

        return files, total_add, total_del

    def has_staged_changes(self, path: Optional[str] = None) -> bool:
        """Return True if index has staged changes."""
        path = path or self.path
        code, _, _ = self.executor.exec(
            "git diff --cached --quiet", flags=REPLY | SILENT, cwd=path
        )
        # --quiet: exit 0 = no differences, 1 = differences exist
        if code == 0:
            return False
        if code == 1:
            return True
        raise RepoError(f"git diff --cached failed with exit code {code}")

    def open_repo_in_browser(
        self,
        path: Optional[str] = None,
        branch: str = "",
        issue: str = "",
        commit: str = "",
        print: bool = False,
    ) -> tuple[bool, str]:
        path = path or self.path
        remote_url = self.get_remote_url(path=path)

        if branch:
            branch = f"/tree/{branch}"
            remote_url += branch
        elif issue:
            issue = f"/issues/{issue}"
            remote_url += issue
        elif commit:
            commit = f"/commit/{commit}"
            remote_url += commit

        if print:
            return True, f"Remote URL: `{remote_url}`<sky_blue>"

        try:
            import webbrowser

            webbrowser.open(remote_url)
        except Exception as e:
            return False, f"Failed to open the repo; {e}"
        else:
            return True, "Successfully opened repo."
