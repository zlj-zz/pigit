"""
Module: pigit/viewmodels/status.py
Description: StatusPanel ViewModel.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Callable

from .base import ActionResult, IListViewModel, ViewModelBase

if TYPE_CHECKING:
    from pigit.git.local_git import LocalGit
    from pigit.git.model import File
    from pigit.app_inspector import FileInfo


class IStatusViewModel(IListViewModel["File"]):
    """Protocol for StatusPanel's ViewModel."""

    @property
    def repo_path(self) -> str: ...
    def stage(self, idx: int) -> ActionResult: ...
    def discard(self, idx: int) -> ActionResult: ...
    def ignore(self, idx: int) -> ActionResult: ...
    def checkout_ours(self, idx: int) -> ActionResult: ...
    def checkout_theirs(self, idx: int) -> ActionResult: ...
    def load_diff(self, idx: int, plain: bool = True) -> list[str]: ...
    def get_inspector_data(self, idx: int) -> FileInfo | None: ...
    def stage_indices(self, indices: set[int]) -> ActionResult: ...
    def discard_indices(self, indices: set[int]) -> ActionResult: ...
    def ignore_indices(self, indices: set[int]) -> ActionResult: ...


class StatusViewModel(ViewModelBase["File"]):
    """Concrete ViewModel for working tree status."""

    def __init__(self, git: LocalGit) -> None:
        super().__init__()
        self._git = git

    @property
    def repo_path(self) -> str:
        return self._git.path or ""

    def _do_load(self) -> list[File]:
        return self._git.load_status()

    def _file_at(self, idx: int) -> File | None:
        items = self._items.value
        if 0 <= idx < len(items):
            return items[idx]
        return None

    def _run_single(
        self,
        idx: int,
        op: Callable[[File], None],
        success_msg: Callable[[File], str],
        guard: Callable[[File], bool] | None = None,
    ) -> ActionResult:
        """Execute a single-file git operation and return an ActionResult."""
        f = self._file_at(idx)
        if f is None:
            return ActionResult(success=False, message="Invalid index")
        if guard is not None and not guard(f):
            return ActionResult(success=False, message="No conflicts")
        try:
            op(f)
            return ActionResult(
                success=True, message=success_msg(f), should_refresh=True
            )
        except Exception as e:
            return ActionResult(success=False, message=str(e))

    def _run_batch(
        self,
        indices: set[int],
        op: Callable[[File], None],
        msg_template: str,
    ) -> ActionResult:
        """Execute a batch git operation and return an ActionResult."""
        items = self._items.value
        count = 0
        try:
            for idx in sorted(indices):
                if idx < len(items):
                    op(items[idx])
                    count += 1
        except Exception as e:
            return ActionResult(success=False, message=str(e))
        return ActionResult(
            success=True, message=msg_template.format(count), should_refresh=count > 0
        )

    def stage(self, idx: int) -> ActionResult:
        return self._run_single(
            idx,
            self._git.switch_file_status,
            lambda f: f"{'Unstaged' if f.has_staged_change else 'Staged'} {f.name}",
        )

    def discard(self, idx: int) -> ActionResult:
        return self._run_single(
            idx,
            self._git.discard_file,
            lambda f: f"Discarded {f.name}",
        )

    def ignore(self, idx: int) -> ActionResult:
        return self._run_single(
            idx,
            self._git.ignore_file,
            lambda f: f"Ignored {f.name}",
        )

    def checkout_ours(self, idx: int) -> ActionResult:
        def _op(f: File) -> None:
            self._git.checkout_ours(f)
            self._git.add_file(f)

        return self._run_single(
            idx,
            _op,
            lambda _f: "Ours",
            guard=lambda f: f.has_merged_conflicts,
        )

    def checkout_theirs(self, idx: int) -> ActionResult:
        def _op(f: File) -> None:
            self._git.checkout_theirs(f)
            self._git.add_file(f)

        return self._run_single(
            idx,
            _op,
            lambda _f: "Theirs",
            guard=lambda f: f.has_merged_conflicts,
        )

    def load_diff(self, idx: int, plain: bool = True) -> list[str]:
        f = self._file_at(idx)
        if f is None:
            return []
        cached = f.has_staged_change and not f.has_unstaged_change
        text = self._git.load_file_diff(f.name, f.tracked, cached, plain=plain)
        return text.splitlines()

    def get_inspector_data(self, idx: int) -> FileInfo | None:
        f = self._file_at(idx)
        if f is None:
            return None
        size, mtime = self._git.get_file_info(f)
        from pigit.app_inspector import FileInfo

        return FileInfo(file=f, size=size, mtime=mtime)

    def stage_indices(self, indices: set[int]) -> ActionResult:
        return self._run_batch(
            indices, self._git.switch_file_status, "Updated {} file(s)"
        )

    def discard_indices(self, indices: set[int]) -> ActionResult:
        return self._run_batch(indices, self._git.discard_file, "Discarded {} file(s)")

    def ignore_indices(self, indices: set[int]) -> ActionResult:
        return self._run_batch(indices, self._git.ignore_file, "Ignored {} file(s)")
