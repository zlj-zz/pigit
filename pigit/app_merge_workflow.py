"""
Module: pigit/app_merge_workflow.py
Description: Branch-merge workflow with continue-merge and push confirmation.
Author: Zev
Date: 2026-08-24
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from collections.abc import Callable

from pigit.app_branch import BranchPanel
from pigit.app_merge_state import MergeStateStore
from pigit.app_network_git import NetworkGit
from pigit.git.api import GitApi, GitError, RepoError
from pigit.termui import FeedbackKind, hide_spinner, show_spinner, show_toast
from pigit.termui import AsyncTask
from pigit.termui.widgets import AlertDialog
from pigit.viewmodels.base import WorktreeGate

from .app_bisect import (
    guard_bisect_active,
    guard_sequencer_active,
    guard_worktree_busy,
)


@dataclass
class MergeStepOutcome:
    """Result of the checkout → pull → merge sequence run on a worker."""

    ok: bool
    step: str = ""
    message: str = ""
    conflict: bool = False
    pre_sha: str = ""
    #: Set when the best-effort checkout back to source also failed.
    checkout_back_failed: str = ""


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
        get_record_rewind: Callable[[], Callable[[str, str], None]],
        get_worktree_gate: Callable[[], WorktreeGate],
        get_merge_task: Callable[[], AsyncTask[MergeStepOutcome]],
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
            get_record_rewind: Late-bound recorder for successful HEAD moves.
            get_worktree_gate: Session gate for working-tree rewrites.
            get_merge_task: Worker that runs the merge sequence off the UI thread.
        """
        self._store = store
        self._network = network
        self._get_git = get_git
        self._navigate_product = navigate_product
        self._get_branch_panel = get_branch_panel
        self._get_alert_dialog = get_alert_dialog
        self._get_refresh_git_vms = get_refresh_git_vms
        self._get_schedule_reload_header = get_schedule_reload_header
        self._get_record_rewind = get_record_rewind
        self._get_worktree_gate = get_worktree_gate
        self._get_merge_task = get_merge_task
        #: True only while THIS workflow holds the session worktree gate.
        #: The completion callback must never release a gate it did not take.
        self._holds_worktree_gate = False

    def on_merge_request(self, source: str, target: str) -> None:
        """Callback from BranchPanel: confirm then execute merge workflow."""
        git = self._get_git()
        if guard_bisect_active(git):
            return
        if guard_sequencer_active(git):
            return
        # A merge is three subprocesses and a HEAD move; starting it on top of
        # a checkout that is still running leaves the worktree half of each.
        if guard_worktree_busy(self._get_worktree_gate().busy):
            return

        def on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            gate = self._get_worktree_gate()
            if not gate.acquire():
                # Lost a race with another rewrite since the entry check.
                guard_worktree_busy(gate.busy)
                return
            self._holds_worktree_gate = True
            # A single label for the whole sequence: a worker cannot update
            # the spinner text, so the per-step messages collapse into one.
            show_spinner(f"Merging {source} into {target}")

            def done(outcome: MergeStepOutcome) -> None:
                self._release_worktree_gate()
                hide_spinner()
                self._apply_merge_outcome(outcome, source, target)

            self._get_merge_task().start(
                lambda: self._merge_worker(source, target),
                done,
                label="Merge",
            )

        self._get_alert_dialog().alert(f"Merge {source} into {target}?", on_confirm)

    def _release_worktree_gate(self) -> None:
        """Release the session gate, but only if this workflow took it."""
        if not self._holds_worktree_gate:
            return
        self._holds_worktree_gate = False
        self._get_worktree_gate().release()

    def _merge_worker(self, source: str, target: str) -> MergeStepOutcome:
        """checkout target → pull → merge source, on a worker thread.

        Never raises. ``AsyncTask`` reports a failure to its error callback
        rather than to ``done``, so anything escaping here would leave the
        worktree gate held and repo switching locked for the whole session.
        """
        try:
            return self._merge_steps(source, target)
        except Exception as exc:
            # Last line of defence: ``AsyncTask`` sends a failure to the error
            # callback instead of ``done``, so anything escaping here would
            # leave the worktree gate held for the rest of the session.
            logging.exception("Merge sequence failed with unexpected error")
            return MergeStepOutcome(
                ok=False, step="merge", message=str(exc), conflict=False
            )

    def _merge_steps(self, source: str, target: str) -> MergeStepOutcome:
        """The sequence itself; see :meth:`_merge_worker` for the contract."""
        git = self._get_git()
        steps = [
            ("checkout", lambda: git.checkout_branch(target)),
            ("pull", lambda: git.pull()),
        ]
        for step, run in steps:
            try:
                run()
            except Exception as exc:
                return self._merge_failure(source, step, exc)
        # The merge is the one HEAD-moving step: capture the pre-merge SHA so
        # the operation stays reversible. Conflicts are never recorded.
        try:
            pre_sha = git.resolve_head_sha()
            git.merge(source)
        except Exception as exc:
            return self._merge_failure(source, "merge", exc)
        return MergeStepOutcome(ok=True, pre_sha=pre_sha)

    def _merge_failure(
        self, source: str, step: str, exc: Exception
    ) -> MergeStepOutcome:
        """Fold a failed step into an outcome, checking out back first."""
        message = str(exc)
        return MergeStepOutcome(
            ok=False,
            step=step,
            message=message,
            conflict="conflict" in message.lower(),
            checkout_back_failed=self._try_checkout_back(source),
        )

    def _apply_merge_outcome(
        self, outcome: MergeStepOutcome, source: str, target: str
    ) -> None:
        """Report a finished merge sequence; runs on the main thread."""
        if not outcome.ok:
            if outcome.checkout_back_failed:
                show_toast(
                    outcome.checkout_back_failed,
                    duration=4.0,
                    kind=FeedbackKind.ERROR,
                )
            if outcome.conflict:
                self._store.set_branch_conflict(source, target)
                show_toast(
                    "Conflict! Resolve in Status, then continue-merge",
                    duration=3.0,
                    kind=FeedbackKind.WARNING,
                )
                self._navigate_product("status")
                return
            show_toast(
                f"Merge {outcome.step} failed: {outcome.message}",
                duration=3.0,
                kind=FeedbackKind.ERROR,
            )
            return
        self._get_record_rewind()(f"Merge {source} into {target}", outcome.pre_sha)
        self.confirm_push_and_finish(target, source)

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
        # Reached after the push worker finished, so the event loop has been
        # running again in between: another rewrite may have started since the
        # entry check in on_merge_request.
        if guard_worktree_busy(self._get_worktree_gate().busy):
            return
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
            # Gated even though it stays synchronous: the gate is a
            # consistency primitive, not a timing one. Committing while a
            # worker rewrites the index can capture a half-applied tree —
            # git's index.lock prevents corruption, not that.
            gate = self._get_worktree_gate()
            if not gate.acquire():
                guard_worktree_busy(gate.busy)
                return
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
            finally:
                gate.release()

        if mode == "pull":
            self._store.clear()
            self._get_refresh_git_vms()
            self._get_schedule_reload_header()
            show_toast("Pull completed", duration=2.0, kind=FeedbackKind.SUCCESS)
            return

        self.confirm_push_and_finish(target, source)

    def _try_checkout_back(self, source: str) -> str:
        """Best-effort checkout back to source branch on failure.

        Runs on the merge worker, so it must not toast — it returns a
        description instead and the main thread reports it. Staying silent
        would leave the user believing they are back on *source* when they are
        not, which is the worst possible moment to hide a second failure.
        """
        try:
            self._get_git().checkout_branch(source)
        except Exception as exc:
            # Best-effort cleanup on an already-failing path: it must never
            # raise, or the exception escapes the worker and the gate is
            # never released.
            return f"Could not return to {source}: {exc}"
        return ""
