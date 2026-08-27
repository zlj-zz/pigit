"""
Module: pigit/app_network_git.py
Description: Async push/pull network git operations with pull-conflict handling.
Author: Zev
Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pigit.app_merge_state import MergeStateStore
from pigit.git.api import GitApi, GitError, RepoError
from pigit.termui import (
    AsyncTask,
    FeedbackKind,
    ToastPosition,
    dismiss_sheet,
    hide_spinner,
    show_spinner,
    show_toast,
)
from pigit.termui.widgets import AlertDialog


@dataclass(frozen=True)
class NetworkGitOutcome:
    """Result of a background push/pull (AsyncTask cannot deliver exceptions)."""

    ok: bool
    message: str = ""
    conflict: bool = False


class NetworkGit:
    """Run push/pull on a worker with spinner; handle pull-merge conflicts.

    Attributes:
        store: MergeStateStore for pull-conflict persistence.
    """

    def __init__(
        self,
        *,
        store: MergeStateStore,
        get_git: Callable[[], GitApi],
        navigate_product: Callable[[str], None],
        get_sync_task: Callable[[], AsyncTask[NetworkGitOutcome]],
        get_refresh_git_vms: Callable[[], None],
        get_schedule_reload_header: Callable[[], None],
        get_alert_dialog: Callable[[], AlertDialog],
    ) -> None:
        """
        Args:
            store: Shared merge session state store.
            get_git: Late-bound GitApi accessor.
            navigate_product: Close Diff detail if open, then route product tab.
            get_sync_task: Late-bound AsyncTask for network sync.
            get_refresh_git_vms: Callback to refresh Status/Branch/Commit VMs.
            get_schedule_reload_header: Callback to reload header branch/ahead/behind.
            get_alert_dialog: Late-bound AlertDialog for set-upstream confirm.
        """
        self._store = store
        self._get_git = get_git
        self._navigate_product = navigate_product
        self._get_sync_task = get_sync_task
        self._get_refresh_git_vms = get_refresh_git_vms
        self._get_schedule_reload_header = get_schedule_reload_header
        self._get_alert_dialog = get_alert_dialog
        self._busy = False

    @property
    def busy(self) -> bool:
        """True while a push/pull worker is in flight."""
        return self._busy

    @busy.setter
    def busy(self, value: bool) -> None:
        self._busy = value

    def run(
        self,
        action: str,
        *,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Run push/pull on a worker with a center spinner; never use exec_external.

        ``on_complete`` runs after the attempt finishes (success or failure), not when
        the busy-guard rejects a second sync. Merge finish uses this to always
        checkout back to ``source``. Cancelled set-upstream alerts also invoke it.
        """
        if action not in ("push", "pull"):
            raise ValueError(f"Unsupported network git action: {action}")
        if self._busy:
            show_toast(
                "Push/Pull already in progress",
                duration=1.5,
                kind=FeedbackKind.INFO,
            )
            return

        if action == "push":
            self._run_push(on_complete=on_complete)
        else:
            self._run_pull(on_complete=on_complete)

    def _run_push(self, *, on_complete: Callable[[], None] | None) -> None:
        """Push with upstream, or confirm ``git push -u`` when none is set."""
        git = self._get_git()
        if git.has_upstream():
            self._start("push", lambda g: g.push(), on_complete=on_complete)
            return

        branch = git.get_current_branch()
        if not branch:
            show_toast(
                "Detached HEAD: checkout a branch before push",
                duration=2.5,
                kind=FeedbackKind.WARNING,
            )
            self._invoke_complete(on_complete)
            return

        remote = git.default_push_remote()
        if not remote:
            show_toast(
                "No remote configured",
                duration=2.5,
                kind=FeedbackKind.WARNING,
            )
            self._invoke_complete(on_complete)
            return

        cmd = f"git push --set-upstream {remote} {branch}"
        message = f"No upstream for '{branch}'.\n\nPush with:\n  {cmd}"

        def on_result(confirmed: bool) -> None:
            if not confirmed:
                self._invoke_complete(on_complete)
                return
            self._start(
                "push",
                lambda g: g.push_set_upstream(remote, branch),
                on_complete=on_complete,
            )

        shown = self._get_alert_dialog().alert(
            message,
            on_result,
            kind=FeedbackKind.WARNING,
        )
        if not shown:
            self._invoke_complete(on_complete)

    def _run_pull(self, *, on_complete: Callable[[], None] | None) -> None:
        """Pull only when the current branch has an upstream."""
        git = self._get_git()
        if not git.has_upstream():
            show_toast(
                "No upstream configured for current branch",
                duration=2.5,
                kind=FeedbackKind.WARNING,
            )
            self._invoke_complete(on_complete)
            return
        self._start("pull", lambda g: g.pull(), on_complete=on_complete)

    def _start(
        self,
        action: str,
        op: Callable[[GitApi], None],
        *,
        on_complete: Callable[[], None] | None,
    ) -> None:
        """Show spinner and run ``op`` on the network sync worker."""
        dismiss_sheet()

        self._busy = True
        label = "Pushing to upstream" if action == "push" else "Pulling from upstream"
        show_spinner(label, position=ToastPosition.CENTER)

        def work() -> NetworkGitOutcome:
            try:
                op(self._get_git())
                return NetworkGitOutcome(ok=True)
            except GitError as exc:
                msg = str(exc)
                return NetworkGitOutcome(
                    ok=False,
                    message=msg,
                    conflict="conflict" in msg.lower(),
                )
            except Exception as exc:
                return NetworkGitOutcome(
                    ok=False,
                    message=f"Git {action} error: {exc}",
                )

        def done(outcome: NetworkGitOutcome) -> None:
            self._busy = False
            hide_spinner()
            try:
                if outcome.conflict:
                    self.handle_pull_conflict(outcome.message)
                    return
                if not outcome.ok:
                    show_toast(
                        outcome.message or f"Git {action} failed",
                        duration=3.0,
                        kind=FeedbackKind.ERROR,
                    )
                    return
                show_toast(
                    f"Git {action} completed",
                    duration=1.5,
                    kind=FeedbackKind.SUCCESS,
                )
                self._get_refresh_git_vms()
                self._get_schedule_reload_header()
            finally:
                self._invoke_complete(on_complete)

        self._get_sync_task().start(work, done)

    @staticmethod
    def _invoke_complete(on_complete: Callable[[], None] | None) -> None:
        if on_complete is not None:
            on_complete()

    def handle_pull_conflict(self, message: str) -> None:
        """Persist pull-merge state, show git detail, and route to Status."""
        git = self._get_git()
        branch = ""
        try:
            branch = git.get_head() or ""
        except (GitError, RepoError):
            branch = ""
        target = branch or "HEAD"
        self._store.set_pull_conflict(target)

        detail = (message or "").strip() or "Merge conflict during pull"
        show_toast(
            f"{detail}\nResolve in Status, then ';' → continue-merge",
            duration=4.0,
            kind=FeedbackKind.WARNING,
        )
        self._navigate_product("status")
        self._get_refresh_git_vms()
