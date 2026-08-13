"""
Module: pigit/git/api/_display.py
Description: Repository information display (repo desc + summary).
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import cast

from pigit.ext.executor import REPLY, DECODE

from ._base import _OpsBase
from ._util import _RE_CONFIG_URL


class _DisplayOps(_OpsBase):
    """Repository information display, orchestrating core + branch data."""

    def __init__(self, api, core, branch) -> None:
        super().__init__(api)
        self._core = core
        self._branch = branch

    def get_summary(self, path: str | None = None, plain: bool = True) -> str:
        path = path or self.path
        color = "never" if plain else "always"
        code, _err, summary = self.executor.exec(
            f"git shortlog --summary --numbered --color={color}",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if code != 0 or summary is None:
            return ""
        return cast(str, summary)

    def get_repo_desc(
        self,
        include_part: list | None = None,
        path: str | None = None,
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
        error_str = "@red(Error getting.)"
        gen = [
            "[@bold(Repository Information)]" if color else "[Repository Information]"
        ]
        repo_path, _ = self._core.confirm_repo(path)

        # Get content.
        if not include_part or "path" in include_part:
            gen.append(
                f"Repository: \n\t@sky_blue({repo_path})\n"
                if color
                else f"Repository: \n\t{repo_path}\n"
            )

        # Get remote url.
        if not include_part or "remote" in include_part:
            try:
                with open(Path(repo_path) / ".git" / "config") as cf:
                    config = cf.read()
            except Exception:
                remote = error_str
            else:
                res = re.findall(_RE_CONFIG_URL, config)
                remote = "\n".join(
                    [f"\t@italic(@sky_blue({x}))" if color else f"\t{x}" for x in res]
                )
            gen.append("Remote: \n%s\n" % remote)

        # Get all branches.
        if not include_part or "branch" in include_part:
            branches = self._branch.get_branches(path, include_remote=True, plain=not color)
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
            git_log = "\t" + error_str if err else textwrap.indent(cast(str, res), "\t")
            gen.append("Latest log:\n%s\n" % git_log)

        # Get git summary.
        if not include_part or "summary" in include_part:
            summary = self.get_summary(path, not color)
            summary_str = (
                "\t" + error_str if not summary else textwrap.indent(summary, "\t")
            )
            gen.append("Summary:\n%s\n" % summary_str)

        return "\n".join(gen)
