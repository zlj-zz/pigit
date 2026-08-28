"""
Module: pigit/app_merge_state.py
Description: Merge session state persistence and header merge_target updates.
Author: Zev
Date: 2026-08-24
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable

from pigit.app_header_state import HeaderState
from pigit.git.api import GitApi, GitError
from pigit.termui import FeedbackKind, show_toast

_MERGE_STATE_FILENAME = "pigit_merge_state"
_DEFAULT_BRANCH_MODE = "branch"
_PULL_MODE = "pull"
_UPSTREAM_SOURCE = "@{upstream}"


class MergeStateStore:
    """Single owner of in-memory merge session state and disk persistence.

    Network pull-conflict and branch-merge workflows read/write through this
    store only. Header ``merge_target`` stays in sync with active merge state.

    Attributes:
        state: Current in-memory merge dict, or None when idle.
    """

    def __init__(
        self,
        header_state: HeaderState,
        get_git_dir: Callable[[], str],
    ) -> None:
        """
        Args:
            header_state: Header display state for merge_target updates.
            get_git_dir: Callable returning the git directory path; may raise GitError.
        """
        self._header_state = header_state
        self._get_git_dir = get_git_dir
        self._state: dict | None = None

    @property
    def state(self) -> dict | None:
        """Current in-memory merge session state."""
        return self._state

    def set_state(self, state: dict | None) -> None:
        """Replace in-memory state and sync header merge_target."""
        self._state = state
        if state is None:
            self._header_state.merge_target = ""
        else:
            self._header_state.merge_target = state.get("target", "")

    def set_pull_conflict(self, target: str) -> None:
        """Record pull-merge conflict state and persist to disk."""
        state = {
            "source": _UPSTREAM_SOURCE,
            "target": target,
            "mode": _PULL_MODE,
        }
        self.set_state(state)
        self.save(_UPSTREAM_SOURCE, target, mode=_PULL_MODE)

    def set_branch_conflict(self, source: str, target: str) -> None:
        """Record branch-merge conflict state and persist to disk."""
        state = {"source": source, "target": target}
        self.set_state(state)
        self.save(source, target)

    def clear(self) -> None:
        """Clear in-memory state, header merge_target, and on-disk snapshot."""
        self.set_state(None)
        self._clear_disk()

    def save(
        self, source: str, target: str, *, mode: str = _DEFAULT_BRANCH_MODE
    ) -> None:
        """
        Persist merge session metadata under the git directory.

        Args:
            source: Merge source ref (branch name or upstream marker).
            target: Merge target branch name.
            mode: Workflow mode (``branch`` or ``pull``).
        """
        try:
            with open(self._state_path(), "w") as file_handle:
                json.dump(
                    {"source": source, "target": target, "mode": mode}, file_handle
                )
        except Exception:
            pass

    def load(self) -> dict | None:
        """
        Load merge session metadata from disk.

        Returns:
            Parsed state dict, or None when missing or invalid.
        """
        try:
            with open(self._state_path()) as file_handle:
                data = json.load(file_handle)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        # Older files omit mode; treat as branch-merge workflow.
        data.setdefault("mode", _DEFAULT_BRANCH_MODE)
        return data

    def rebind(self, git: GitApi) -> None:
        """Point persistence at ``git``'s directory after a repo session switch.

        Clears in-memory / header merge_target, then restores from the new
        git dir when a merge is still in progress there.
        """
        self._get_git_dir = git.get_git_dir
        self.set_state(None)
        if git.is_merge_in_progress():
            self.try_restore(git.is_merge_in_progress)

    def try_restore(self, is_merge_in_progress: Callable[[], bool]) -> None:
        """On startup: recover pending merge state if merge is still in progress.

        Swallows GitError (e.g. not a git repo) — merge state restoration is
        best-effort and should never prevent the TUI from starting.

        Args:
            is_merge_in_progress: Callable reporting whether Git merge is active.
        """
        try:
            state = self.load()
        except GitError:
            return
        if state is None:
            return
        if is_merge_in_progress():
            self.set_state(state)
            mode = state.get("mode", _DEFAULT_BRANCH_MODE)
            if mode == _PULL_MODE:
                show_toast(
                    "Resume pull merge (continue-merge)",
                    duration=3.0,
                    kind=FeedbackKind.INFO,
                )
            else:
                show_toast(
                    f"Resume merge: {state['source']} → {state['target']} (continue-merge)",
                    duration=3.0,
                    kind=FeedbackKind.INFO,
                )
        else:
            self._clear_disk()
            self._header_state.merge_target = ""

    def synthesize_pull_state(self, target: str) -> dict:
        """
        Build pull-mode merge state when Git merge is active but disk state is missing.

        Args:
            target: Current HEAD branch name (or ``HEAD`` fallback).

        Returns:
            Pull merge state dict suitable for ``set_state``.
        """
        return {
            "source": _UPSTREAM_SOURCE,
            "target": target,
            "mode": _PULL_MODE,
        }

    def _state_path(self) -> str:
        """Return the path to the persistent merge state file."""
        git_dir = self._get_git_dir()
        return os.path.join(git_dir, _MERGE_STATE_FILENAME)

    def _clear_disk(self) -> None:
        """Remove persisted merge state file if present."""
        try:
            os.remove(self._state_path())
        except FileNotFoundError:
            pass
