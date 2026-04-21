# -*- coding:utf-8 -*-

import logging
import os
import re
import time
import shutil
import textwrap
from typing import Iterator, Optional, Union

from plenty.str_utils import shorten, byte_str2str
from plenty.console import Console

from pigit.ext.executor import SILENT, WAITING, REPLY, DECODE, Executor
from pigit.ext.utils import adjudgment_type, get_file_icon
from .model import File, Commit, Branch


class RepoError(Exception):
    """Error class of ~GitOption."""


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
        path = os.path.abspath(path)

        repo_path: str = ""
        git_conf_path: str = ""

        if not os.path.isdir(path):
            return repo_path, git_conf_path

        code, _err, top_out = self.executor.exec(
            "git rev-parse --show-toplevel",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if code is None or code != 0 or not top_out or not str(top_out).strip():
            return "", ""

        repo_path = os.path.abspath(str(top_out).strip())

        code2, _err2, gd_out = self.executor.exec(
            "git rev-parse --git-dir",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if code2 is None or code2 != 0 or not gd_out or not str(gd_out).strip():
            return "", ""

        git_dir_raw = str(gd_out).strip()
        if os.path.isabs(git_dir_raw):
            git_conf_path = os.path.normpath(git_dir_raw)
        else:
            git_conf_path = os.path.normpath(os.path.join(repo_path, git_dir_raw))

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
            with open(f"{config_path}/config", "r") as cf:
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

        command = "git merge-base %s %s@{u}" % (branch_name, branch_name)
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
            f"git ls-remote --get-url {remote_name}", flags=REPLY | DECODE, cwd=path
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
                with open(f"{repo_path}/.git/config", "r") as cf:
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
    def load_branches(self, path: Optional[str] = None) -> list[Branch]:
        path = path or self.path
        branches = []

        _, _, resp = self.executor.exec(
            "git branch --sort=-committerdate "
            '--format="%(HEAD)|%(refname:short)|%(upstream:short)|%(upstream:track)" ',
            flags=REPLY | DECODE,
            cwd=path,
        )
        resp = resp.strip()
        if not resp:
            return branches

        lines = resp.split("\n")

        for line in lines:
            items = line.split("|")
            branch = Branch(
                name=items[1], ahead="?", behind="?", is_head=items[0] == "*"
            )

            upstream_name = items[2]

            if not upstream_name:
                branches.append(branch)
                continue

            branch.upstream_name = upstream_name

            track = items[3]
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

        _, _, resp = self.executor.exec(
            f"git log {branch_name} {arg_str} {limit_flag} {filter_flag}",
            flags=REPLY | DECODE,
            cwd=path,
        )

        return "" if resp is None else resp.strip()

    @staticmethod
    def _find_dot_git_dir(cwd: str) -> Optional[str]:
        cur = os.path.abspath(cwd)
        while True:
            git = os.path.join(cur, ".git")
            if os.path.isdir(git):
                return git
            if os.path.isfile(git):
                return None
            parent = os.path.dirname(cur)
            if parent == cur:
                return None
            cur = parent

    def _load_status_cache_signature(
        self, cwd: str
    ) -> Optional[tuple[int, int, int, int, bool]]:
        git_dir = self._find_dot_git_dir(cwd)
        if not git_dir:
            return None

        def st(p: str) -> tuple[int, int]:
            try:
                s = os.stat(p)
                return (s.st_mtime_ns, s.st_size)
            except OSError:
                return (0, 0)

        index_p = os.path.join(git_dir, "index")
        head_p = os.path.join(git_dir, "HEAD")
        merge = os.path.join(git_dir, "MERGE_HEAD")
        i0, i1 = st(index_p)
        h0, h1 = st(head_p)
        return (i0, i1, h0, h1, os.path.exists(merge))

    def load_status(
        self,
        max_width: int = 80,
        ident: int = 2,
        plain: bool = False,
        path: Optional[str] = None,
        icon: bool = False,
        use_cache: bool = True,
    ) -> list[File]:
        """Get the file tree status of GIT for processing and encapsulation.

        Args:
                max_width (int): The max length of display string.
                ident (int, option): Number of reserved blank characters in the header.
                use_cache (bool): When True, reuse recent result if git metadata unchanged
                    and within a short TTL (see class constant ``_LOAD_STATUS_CACHE_TTL``).

        Returns:
                (list[File]): Processed file status list.
        """
        path = path or self.path
        if path is None or path == "":
            workdir = os.path.abspath(".")
        else:
            workdir = os.path.abspath(path)

        key = (workdir, max_width, ident, plain, icon)
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

            display_name = shorten(name, max_width - 3 - ident)

            icon_str = get_file_icon(adjudgment_type(display_name)) if icon else ""

            # color full command.
            display_str = Console.render_str(
                f"`{staged_change}`<{'bad' if has_no_staged_change else'right'}>`{unstaged_change}`<{'bad' if unstaged_change!=' ' else'right'}> {icon_str}{display_name}"
            )

            file_ = File(
                name=name,
                display_str=file if plain else display_str,
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
            f"git diff --submodule --no-ext-diff {_plain} {_cached} {_tracked} {file}",
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

        limit_flag = f"-n {max_commits}" if limit else ""
        filter_flag = f"--follow -- {filter_path}" if filter_path else ""
        command = (
            f'git log {branch_name} --oneline --pretty=format:"%H|%at|%aN|%d|%p|%s" '
            f"{limit_flag} --abbrev=20 --date=unix {filter_flag}"
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
            message = "|".join(split_[5:])

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

        _, _, resp = self.executor.exec(
            f"git show --color={color_str} {commit_sha} {file_name}",
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
                f"git add -- '{file_name}'", flags=WAITING | SILENT, cwd=path
            )
        elif file.has_staged_change:
            if file.tracked:
                self.executor.exec(
                    f"git reset HEAD -- '{file_name}'",
                    flags=WAITING | SILENT,
                    cwd=path,
                )
            else:
                self.executor.exec(
                    f"git rm --cached --force -- '{file_name}'",
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
        lookup = os.path.abspath(lookup)

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
                f"git checkout -- '{file_name}'",
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
            abs_file = os.path.normpath(os.path.join(repo_root, file_name))
            if not os.path.lexists(abs_file):
                self.log.info("discard_file: skip missing untracked path %r", abs_file)
                return
            if os.path.isdir(abs_file) and not os.path.islink(abs_file):
                shutil.rmtree(abs_file)
            else:
                os.remove(abs_file)

    def ignore_file(self, file: Union[File, str], path: Optional[str] = None):
        """Append file to `.gitignore` file."""

        path = path or self.path
        repo_path, _ = self.confirm_repo(path)
        file_name = _file_path_for_cmd(file)

        with open(f"{repo_path}/.gitignore", "a+") as f:
            f.write(f"\n{file_name}")

    def checkout_branch(self, branch_name: str, path: Optional[str] = None) -> str:
        path = path or self.path
        code, err, out = self.executor.exec(
            f"git checkout {branch_name}", cwd=path, flags=WAITING | REPLY | DECODE
        )
        return err or "ok"

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
