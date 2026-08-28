"""
Module: pigit/app_sequencer.py
Description: Rebase/cherry-pick/revert sequencer control and cherry-pick execution.
Author: Zev
Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Callable

from pigit.git.api import GitApi, GitError, RepoError
from pigit.termui import (
    FeedbackKind,
    dismiss_sheet,
    exec_external,
    show_badge,
    show_sheet,
    show_toast,
)
from pigit.termui.widgets import AlertDialog

_SEQUENCER_PAUSED = {
    "rebase": "Rebase paused. Resolve/edit, then ';' → rebase-continue/abort/skip",
    "cherry-pick": "Cherry-pick paused. Resolve, then ';' → cherry-pick-continue/abort/skip",
    "revert": "Revert paused. Resolve, then ';' → cherry-pick-continue/abort/skip",
}


class SequencerControl:
    """Rebase/cherry-pick/revert control, cherry-pick exec/finish, pause messaging.

    Attributes:
        get_git: Late-bound GitApi accessor.
        get_repo_path: Callable returning repository root for exec_external cwd.
    """

    def __init__(
        self,
        *,
        get_git: Callable[[], GitApi],
        get_repo_path: Callable[[], str],
        navigate_product: Callable[[str], None],
        get_alert_dialog: Callable[[], AlertDialog],
        get_refresh_git_vms: Callable[[], None],
        get_refresh_active_panel: Callable[[], None],
    ) -> None:
        """
        Args:
            get_git: Late-bound GitApi accessor.
            get_repo_path: Callable returning cwd for exec_external.
            navigate_product: Close Diff detail if open, then route product tab.
            get_alert_dialog: Late-bound AlertDialog accessor.
            refresh_git_vms: Callback to refresh Status/Branch/Commit VMs.
            refresh_active_panel: Callback after rebase sheet completes.
        """
        self._get_git = get_git
        self._get_repo_path = get_repo_path
        self._navigate_product = navigate_product
        self._get_alert_dialog = get_alert_dialog
        self._get_refresh_git_vms = get_refresh_git_vms
        self._get_refresh_active_panel = get_refresh_active_panel

    def on_rebase_request(self, target: str) -> None:
        """Open the interactive-rebase todo panel for ``target``."""
        from pigit.app_rebase import RebasePanel

        def _on_done() -> None:
            dismiss_sheet()
            self._get_refresh_active_panel()

        panel = RebasePanel(self._get_git(), target, on_done=_on_done)
        show_sheet(panel, max_fraction=0.5, title="Rebase")
        panel.mount()

    def run_git_action(self, action: str) -> None:
        """Run a git action via exec_external and show result toast."""
        try:
            result = exec_external(["git", action], cwd=self._get_repo_path())
            if result.returncode == 0:
                show_toast(
                    f"Git {action} completed", duration=1.5, kind=FeedbackKind.SUCCESS
                )
            else:
                stderr = result.stderr.strip() if result.stderr else "Unknown error"
                show_toast(
                    f"Git {action} failed: {stderr}",
                    duration=3.0,
                    kind=FeedbackKind.ERROR,
                )
        except Exception as exc:
            show_toast(
                f"Git {action} error: {exc}", duration=3.0, kind=FeedbackKind.ERROR
            )

    def run_rebase_control(self, action: str) -> None:
        """Run a rebase control flag (--continue/--abort/--skip)."""
        flag = action[len("rebase-") :]
        if flag == "abort":

            def on_confirm(confirmed: bool) -> None:
                if confirmed:
                    self.do_rebase_control(flag)

            self._get_alert_dialog().alert(
                "Abort rebase? All progress will be lost.",
                on_confirm,
                kind=FeedbackKind.WARNING,
            )
            return
        self.do_rebase_control(flag)

    def do_rebase_control(self, flag: str) -> None:
        """Execute ``git rebase --<flag>`` via exec_external and refresh panels."""
        try:
            result = exec_external(
                ["git", "rebase", f"--{flag}"], cwd=self._get_repo_path()
            )
        except Exception as exc:
            show_toast(
                f"Rebase {flag} error: {exc}", duration=3.0, kind=FeedbackKind.ERROR
            )
            return
        self._after_external_git(
            result,
            flag=flag,
            done_msg=f"Rebase {flag} completed",
            failed_msg=f"Rebase {flag} failed",
        )

    def run_cherry_pick_control(self, action: str) -> None:
        """Run a cherry-pick control flag (--continue/--abort/--skip)."""
        flag = action[len("cherry-pick-") :]
        if flag == "abort":

            def on_confirm(confirmed: bool) -> None:
                if confirmed:
                    self.do_cherry_pick_control(flag)

            self._get_alert_dialog().alert(
                "Abort cherry-pick? All progress will be lost.",
                on_confirm,
                kind=FeedbackKind.WARNING,
            )
            return
        self.do_cherry_pick_control(flag)

    def do_cherry_pick_control(self, flag: str) -> None:
        """Execute ``git cherry-pick --<flag>`` via exec_external."""
        argv = ["git", "cherry-pick", f"--{flag}"]
        if flag == "continue":
            argv.append("--no-edit")
        try:
            result = exec_external(argv, cwd=self._get_repo_path())
        except Exception as exc:
            show_toast(
                f"Cherry-pick {flag} error: {exc}",
                duration=3.0,
                kind=FeedbackKind.ERROR,
            )
            return
        self._after_external_git(
            result,
            flag=flag,
            done_msg=f"Cherry-pick {flag} completed",
            failed_msg=f"Cherry-pick {flag} failed",
        )

    def on_cherry_pick(self, sha: str, is_merge: bool) -> None:
        """Guard, confirm, then copy ``sha`` onto HEAD via exec_external."""
        from .app_bisect import guard_bisect_active, guard_sequencer_active

        git = self._get_git()
        if guard_bisect_active(git):
            return
        if guard_sequencer_active(git):
            return
        try:
            if sha == git.resolve_head_sha():
                show_toast(
                    "Already at this commit",
                    duration=2.0,
                    kind=FeedbackKind.WARNING,
                )
                return
            if is_merge:
                show_toast(
                    "Cannot cherry-pick a merge commit",
                    duration=2.0,
                    kind=FeedbackKind.WARNING,
                )
                return
        except (GitError, RepoError) as exc:
            show_toast(str(exc), duration=2.0, kind=FeedbackKind.ERROR)
            return

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                self.exec_cherry_pick(sha)

        self._get_alert_dialog().alert(
            f"Cherry-pick {sha[:7]} onto current HEAD?",
            on_confirm,
        )

    def exec_cherry_pick(self, sha: str) -> None:
        """Run ``git cherry-pick`` after the user confirmed."""
        try:
            result = exec_external(
                ["git", "cherry-pick", sha], cwd=self._get_repo_path()
            )
        except Exception as exc:
            show_toast(
                f"Cherry-pick error: {exc}", duration=3.0, kind=FeedbackKind.ERROR
            )
            return
        self.finish_cherry_pick(result, sha)

    def finish_cherry_pick(self, result, sha: str) -> None:
        """Toast or badge the outcome of a just-run cherry-pick."""
        git = self._get_git()
        try:
            kind = git.sequencer_in_progress()
            if result.returncode == 0:
                show_badge(f"Cherry-picked {sha[:7]}")
                self._get_refresh_git_vms()
                return
            if kind == "cherry-pick":
                if git.has_unmerged_paths():
                    show_toast(
                        "Conflict! Resolve in Status, then ';' → cherry-pick-continue/abort",
                        duration=3.0,
                        kind=FeedbackKind.WARNING,
                    )
                    self._navigate_product("status")
                else:
                    show_toast(
                        "Cherry-pick is empty. ';' → cherry-pick-skip or cherry-pick-abort",
                        duration=3.0,
                        kind=FeedbackKind.WARNING,
                    )
                return
        except (GitError, RepoError) as exc:
            show_toast(str(exc), duration=2.0, kind=FeedbackKind.ERROR)
            return
        show_toast("Cherry-pick failed", duration=2.0, kind=FeedbackKind.ERROR)
        self._get_refresh_git_vms()

    def _after_external_git(
        self,
        result,
        *,
        flag: str,
        done_msg: str,
        failed_msg: str,
    ) -> None:
        """Toast and refresh after an exec_external sequencer command.

        git's sequencer is shared, so a revert is resumed via
        ``cherry-pick-continue``; the paused state is labeled by the actual
        sequencer kind, not the command that was run.
        """
        still = self._get_git().sequencer_in_progress()
        if result.returncode == 0:
            if still is not None:
                show_toast(
                    _SEQUENCER_PAUSED.get(still, f"{still} paused"),
                    duration=3.0,
                    kind=FeedbackKind.WARNING,
                )
            else:
                show_toast(done_msg, duration=1.5, kind=FeedbackKind.SUCCESS)
            self._get_refresh_git_vms()
            return
        show_toast(failed_msg, duration=2.0, kind=FeedbackKind.ERROR)
