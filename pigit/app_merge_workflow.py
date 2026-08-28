"""
Module: pigit/app_merge_workflow.py
Description: Branch-merge workflow with continue-merge and push confirmation.
Author: Zev
Date: 2026-08-24
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from pigit.app_branch import BranchPanel
from pigit.app_merge_state import MergeStateStore
from pigit.app_network_git import NetworkGit
from pigit.git.api import GitApi, GitError, RepoError
from pigit.termui import FeedbackKind, hide_spinner, show_spinner, show_toast
from pigit.termui.widgets import AlertDialog


class MergeWorkflow:
    """Branch merge request, continue-merge, and finish/push confirmation.

    Attributes:
        store: MergeStateStore for session state.
        network: NetworkGit for push after merge.
    """

    def __init__(
        self,
        *,
        store: MergeStateStore,
        network: NetworkGit,
        get_git: Callable[[], GitApi],
        navigate_product: Callable[[str], None],
        get_branch_panel: Callable[[], BranchPanel],
        get_alert_dialog: Callable[[], AlertDialog],
        get_refresh_git_vms: Callable[[], None],
        get_schedule_reload_header: Callable[[], None],
    ) -> None:
        """
        Args:
            store: Shared merge session state store.
            network: NetworkGit collaborator for post-merge push.
            get_git: Late-bound GitApi accessor.
            navigate_product: Close Diff detail if open, then route product tab.
            get_branch_panel: Late-bound BranchPanel accessor.
            get_alert_dialog: Late-bound AlertDialog accessor.
            refresh_git_vms: Callback to refresh Status/Branch/Commit VMs.
            schedule_reload_header: Callback to reload header branch/ahead/behind.
        """
        self._store = store
        self._network = network
        self._get_git = get_git
        self._navigate_product = navigate_product
        self._get_branch_panel = get_branch_panel
        self._get_alert_dialog = get_alert_dialog
        self._get_refresh_git_vms = get_refresh_git_vms
        self._get_schedule_reload_header = get_schedule_reload_header

    def on_merge_request(self, source: str, target: str) -> None:
        """Callback from BranchPanel: confirm then execute merge workflow."""
        from .app_bisect import guard_bisect_active

        git = self._get_git()
        if guard_bisect_active(git):
            return
        kind = git.sequencer_in_progress()
        if kind is not None:
            show_toast(
                f"A {kind} is already in progress",
                duration=2.0,
                kind=FeedbackKind.WARNING,
            )
            return

        def on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self.do_merge_workflow(source, target)
            except GitError as exc:
                hide_spinner()
                err_msg = str(exc).lower()
                if "conflict" in err_msg:
                    self._store.set_branch_conflict(source, target)
                    show_toast(
                        "Conflict! Resolve in Status, then continue-merge",
                        duration=3.0,
                        kind=FeedbackKind.WARNING,
                    )
                    self._navigate_product("status")
                    return
                show_toast(
                    f"Merge failed: {exc}", duration=3.0, kind=FeedbackKind.ERROR
                )
                return
            except Exception:
                hide_spinner()
                logging.exception("Merge workflow failed with unexpected error")
                return
            self.confirm_push_and_finish(target, source)

        self._get_alert_dialog().alert(f"Merge {source} into {target}?", on_confirm)

    def do_merge_workflow(self, source: str, target: str) -> None:
        """Atomically: checkout target → pull → merge source.

        On any step failure, best-effort checkout back to source then raise.
        """
        git = self._get_git()
        steps = [
            (f"Checking out {target}", lambda: git.checkout_branch(target)),
            (f"Pulling {target}", lambda: git.pull()),
            (f"Merging {source}", lambda: git.merge(source)),
        ]
        for msg, step in steps:
            show_spinner(msg)
            try:
                step()
            except GitError:
                hide_spinner()
                self._try_checkout_back(source)
                raise
            except Exception:
                hide_spinner()
                self._try_checkout_back(source)
                raise
        hide_spinner()

    def confirm_push_and_finish(self, target: str, source: str) -> None:
        """Alert confirm push, then checkout back to source branch after push completes."""

        def on_push_confirmed(confirmed: bool) -> None:
            if not confirmed:
                self.finish_merge_checkout(target, source)
                return

            def after_push() -> None:
                self.finish_merge_checkout(target, source)

            self._network.run("push", on_complete=after_push)

        self._get_alert_dialog().alert(f"Push {target} to remote?", on_push_confirmed)

    def finish_merge_checkout(self, target: str, source: str) -> None:
        """Checkout back to source and clear merge state after merge push step."""
        git = self._get_git()
        try:
            git.checkout_branch(source)
        except GitError as exc:
            show_toast(
                f"Checkout back failed: {exc}", duration=3.0, kind=FeedbackKind.ERROR
            )
            return
        self._store.clear()
        self._navigate_product("branch")
        self._get_branch_panel().refresh()
        show_toast(f"Merged into {target}", duration=2.0, kind=FeedbackKind.SUCCESS)

    def continue_merge(self) -> None:
        """Resume a pending merge after conflicts have been resolved."""
        git = self._get_git()
        state = self._store.state
        if state is None and git.is_merge_in_progress():
            branch = ""
            try:
                branch = git.get_head() or ""
            except (GitError, RepoError):
                branch = ""
            state = self._store.synthesize_pull_state(branch or "HEAD")
            self._store.set_state(state)

        if not state:
            show_toast("No pending merge", duration=2.0, kind=FeedbackKind.WARNING)
            return

        target = state["target"]
        source = state["source"]
        mode = state.get("mode", "branch")

        if git.is_merge_in_progress():
            try:
                git.commit_no_edit()
            except GitError as exc:
                err = str(exc).lower()
                if "conflict" in err or "unmerged" in err:
                    show_toast(
                        "Unresolved conflicts remain. Fix in Status, then retry.",
                        duration=3.0,
                        kind=FeedbackKind.WARNING,
                    )
                else:
                    show_toast(
                        f"Merge commit failed: {exc}",
                        duration=3.0,
                        kind=FeedbackKind.ERROR,
                    )
                return

        if mode == "pull":
            self._store.clear()
            self._get_refresh_git_vms()
            self._get_schedule_reload_header()
            show_toast("Pull completed", duration=2.0, kind=FeedbackKind.SUCCESS)
            return

        self.confirm_push_and_finish(target, source)

    def _try_checkout_back(self, source: str) -> None:
        """Best-effort checkout back to source branch on failure."""
        try:
            self._get_git().checkout_branch(source)
        except GitError:
            pass
