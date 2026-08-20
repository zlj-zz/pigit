"""
Module: pigit/git/api/_core.py
Description: Low-level git primitives (repo discovery/config/head) shared by submodules.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import cast

from pigit.ext.executor import WAITING, REPLY, DECODE

from ._base import _OpsBase
from ._errors import GitError
from ._util import _RE_CONFIG_NEWLINE


class _CoreOps(_OpsBase):
    """Repo discovery, config, and head primitives used across the git API."""

    def __init__(self, api) -> None:
        super().__init__(api)

    def confirm_repo(
        self, given_path: str | None = None, exclude_submodule: bool = False
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

    def get_config(self, path: str | None = None) -> dict[str, dict[str, str]]:
        """Try to read git config and parse, return a config dict.

        Args:
            path (Optional[str], optional): repo path. Defaults to None.

        Returns:
            dict[str, dict[str, str]]: config dict.
        """
        path = path or self.path

        _, config_path = self.confirm_repo(path)
        try:
            with open(Path(config_path) / "config") as cf:
                context = cf.read()
        except Exception as e:
            self.log.warning(f"Can not read config with: {e}")
            return {}
        else:
            conf_dict: dict[str, dict[str, str]] = {}
            conf_list = re.split(_RE_CONFIG_NEWLINE, context)
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

    def get_config_value(self, key: str, path: str | None = None) -> str | None:
        """Get a single git config value by key (e.g. ``commit.template``).

        Returns ``None`` if the key is not set.
        """
        path = path or self.path
        code, _err, out = self.executor.exec(
            f"git config {shlex.quote(key)}",
            cwd=path,
            flags=REPLY | DECODE,
        )
        if code != 0 or not out:
            return None
        return cast(str, out).strip()

    def get_head(self, path: str | None = None) -> str | None:
        """Get current repo head. Return a branch name or a commit sha string."""
        path = path or self.path

        _, _, head = self.executor.exec(
            "git symbolic-ref -q --short HEAD || git describe --tags --exact-match",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if head is not None:
            head = cast(str, head).rstrip()
        return head

    def get_first_pushed_commit(
        self, path: str | None = None, branch_name: str | None = None
    ) -> str:
        path = path or self.path

        if branch_name is None:
            if head := self.get_head(path):
                branch_name = head
            else:
                return ""

        command = "git merge-base {} {}@{{u}}".format(
            shlex.quote(branch_name),
            shlex.quote(branch_name),
        )
        _, _, commit_msg = self.executor.exec(command, flags=REPLY | DECODE, cwd=path)
        if commit_msg is None:
            return ""
        return cast(str, commit_msg).strip()

    def get_remotes(self, path: str | None = None) -> list[str]:
        """Get repo remote url."""

        # Get remote name, exit when error.
        path = path or self.path
        _, _, res = self.executor.exec(
            "git remote show", flags=REPLY | DECODE, cwd=path
        )

        return cast(str, res).strip().splitlines() if res else []

    def get_remote_url(
        self, path: str | None = None, remote_name: str | None = None
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

        if err or remote_url is None:
            return ""

        remote_url = cast(str, remote_url)[:-5]
        return remote_url

    @staticmethod
    def _find_dot_git_dir(cwd: str) -> str | None:
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

    def get_git_dir(self, path: str | None = None) -> str:
        """Return the git directory path via ``git rev-parse --git-dir``."""
        path = path or self.path
        code, err, out = self.executor.exec(
            "git rev-parse --git-dir",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if code != 0 or not out:
            raise GitError(err or "Failed to get git directory")
        git_dir_raw = cast(str, out).strip()
        if Path(git_dir_raw).is_absolute():
            return str(Path(git_dir_raw).resolve())
        repo_root, _ = self.confirm_repo(path)
        return str((Path(repo_root) / git_dir_raw).resolve())

    def get_git_common_dir(self, path: str | None = None) -> str:
        """Return the common git directory via ``git rev-parse --git-common-dir``.

        Equals ``get_git_dir`` for a normal repo; differs for linked worktrees.
        """
        path = path or self.path
        code, err, out = self.executor.exec(
            "git rev-parse --git-common-dir",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if code != 0 or not out:
            raise GitError(err or "Failed to get git common directory")
        raw = cast(str, out).strip()
        if Path(raw).is_absolute():
            return str(Path(raw).resolve())
        repo_root, _ = self.confirm_repo(path)
        return str((Path(repo_root) / raw).resolve())

    def get_head_tracking(self, path: str | None = None) -> tuple[str, int, int]:
        """Return ``(branch_or_label, ahead, behind)`` for the current HEAD.

        ``ahead``/``behind`` are relative to ``@{upstream}`` when configured;
        otherwise both are ``0``.
        """
        path = path or self.path
        head = self.get_head(path) or ""
        code, _err, out = self.executor.exec(
            "git rev-list --left-right --count @{upstream}...HEAD",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if code != 0 or not out:
            return head, 0, 0
        parts = cast(str, out).strip().split()
        if len(parts) != 2:
            return head, 0, 0
        try:
            behind = int(parts[0])
            ahead = int(parts[1])
        except ValueError:
            return head, 0, 0
        return head, ahead, behind

    def verify_commitish(self, ref: str, path: str | None = None) -> str:
        """Return the full SHA of ``ref`` if it names a commit.

        Args:
            ref: Commit-ish (branch, remote-tracking name, ``HEAD``, SHA).
            path: Repo path; defaults to ``self.path``.

        Returns:
            Stripped full SHA.

        Raises:
            GitError: When git cannot resolve ``ref`` to a commit.
        """
        path = path or self.path
        spec = shlex.quote(f"{ref}^{{commit}}")
        code, err, out = self.executor.exec(
            f"git rev-parse --verify --end-of-options {spec}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0 or not out:
            raise GitError(err or f"Not a commit: {ref}")
        return cast(str, out).strip()
