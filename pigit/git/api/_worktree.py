"""
Module: pigit/git/api/_worktree.py
Description: Working-tree mutation (stage/discard/ignore/conflict resolution).
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path

from pigit.ext.executor import WAITING, SILENT, REPLY, DECODE

from ..model import File
from ._base import _OpsBase
from ._errors import GitError, RepoError
from ._util import _file_path_for_cmd


class _WorktreeOps(_OpsBase):
    """Working-tree changes: stage, discard, ignore, conflict resolution."""

    def __init__(self, api, core) -> None:
        super().__init__(api)
        self._core = core

    def switch_file_status(self, file: File, path: str | None = None):
        """Change the file stage status.

        Args:
            file (File): git file object.
            path (Optional[str], optional): exec path. Defaults to None.
        """
        path = path or self.path
        file_name = file.get_file_str()

        if (
            file.has_merged_conflicts
            or file.has_inline_merged_conflicts
            or file.has_unstaged_change
        ):
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
        file: File | str,
        path: str | None = None,
        tracked: bool | None = None,
    ):
        lookup = path if path is not None else self.path
        if lookup is None or lookup == "":
            lookup = "."
        lookup = str(Path(lookup).resolve())

        repo_root, _ = self._core.confirm_repo(lookup)
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

    def ignore_file(self, file: File | str, path: str | None = None):
        """Append file to `.gitignore` file."""

        path = path or self.path
        repo_path, _ = self._core.confirm_repo(path)
        file_name = _file_path_for_cmd(file)

        with open(Path(repo_path) / ".gitignore", "a+") as f:
            f.write(f"\n{file_name}")

    def unignore_file(self, file: File | str, path: str | None = None) -> None:
        """Remove file entry from .gitignore."""
        path = path or self.path
        repo_path, _ = self._core.confirm_repo(path)
        file_name = _file_path_for_cmd(file)
        gitignore_path = Path(repo_path) / ".gitignore"
        if not gitignore_path.exists():
            return
        content = gitignore_path.read_text()
        lines = content.splitlines()
        filtered = [line for line in lines if line.strip() != file_name]
        if len(filtered) != len(lines):
            gitignore_path.write_text("\n".join(filtered) + ("\n" if filtered else ""))

    def add_file(self, file: File | str, path: str | None = None) -> None:
        """Stage a file."""
        path = path or self.path
        file_name = _file_path_for_cmd(file)
        code, err, _ = self.executor.exec(
            f"git add -- {shlex.quote(file_name)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or f"add failed: {file_name}")

    def checkout_ours(self, file: File | str, path: str | None = None) -> None:
        """Checkout ``--ours`` version of a conflicted file."""
        path = path or self.path
        file_name = _file_path_for_cmd(file)
        code, err, _ = self.executor.exec(
            f"git checkout --ours -- {shlex.quote(file_name)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or f"checkout --ours failed: {file_name}")

    def checkout_theirs(self, file: File | str, path: str | None = None) -> None:
        """Checkout ``--theirs`` version of a conflicted file."""
        path = path or self.path
        file_name = _file_path_for_cmd(file)
        code, err, _ = self.executor.exec(
            f"git checkout --theirs -- {shlex.quote(file_name)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or f"checkout --theirs failed: {file_name}")

    def checkout_head_file(self, file: File | str, path: str | None = None) -> None:
        """Restore file from HEAD (fallback when blob SHA is unavailable)."""
        path = path or self.path
        file_name = _file_path_for_cmd(file)
        code, err, _ = self.executor.exec(
            f"git checkout HEAD -- {shlex.quote(file_name)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or f"checkout HEAD failed: {file_name}")

    def reset_head_file(self, file: File | str, path: str | None = None) -> None:
        """git reset HEAD -- <file> (unstage)."""
        path = path or self.path
        file_name = _file_path_for_cmd(file)
        code, err, _ = self.executor.exec(
            f"git reset HEAD -- {shlex.quote(file_name)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or f"reset HEAD failed: {file_name}")

    def soft_reset_head1(self, path: str | None = None) -> None:
        """git reset --soft HEAD~1 (uncommit, keep staged)."""
        path = path or self.path
        code, err, _ = self.executor.exec(
            "git reset --soft HEAD~1",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or "soft reset HEAD~1 failed")

    def hard_reset_head(self, sha: str, path: str | None = None) -> None:
        """git reset --hard <sha> (move HEAD, discard worktree changes).

        Only safe on a clean worktree; callers guard on ``status_porcelain``
        before invoking (see ``session_history.rewind_head``).
        """
        path = path or self.path
        code, err, _ = self.executor.exec(
            f"git reset --hard {shlex.quote(sha)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or "hard reset HEAD failed")
