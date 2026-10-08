"""
Module: pigit/app_branch.py
Description: BranchPanel v3 with ahead/behind display and current branch highlighting.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Callable

from pigit.termui import (
    EventType,
    FeedbackKind,
    bind_action,
    bind_signals,
    by_id,
    dismiss_sheet,
    palette,
    run_with_spinner,
    Segment,
    show_badge,
    show_sheet,
    show_toast,
)
from pigit.termui.widgets import (
    ACCENT_BAR,
    AlertDialog,
    InputLine,
    OptionList,
    SectionRule,
)
from pigit.termui.reactive import Signal

from .app_types import BranchSnapshot
from .ext.utils import relative_time
from .app_theme import LOAD_FAILED_MARK, THEME, load_failed_segments
from .app_row_slots import pad_to_width, status_lane
from pigit.termui.wcwidth_table import wcswidth
from .viewmodels.branch import IBranchViewModel
from .viewmodels.base import ActionResult

if TYPE_CHECKING:
    from pigit.git.api import GitApi
    from .git.model import Branch


class BranchPanel(OptionList):
    """Branch panel with ahead/behind display and current branch highlighting."""

    CURSOR = ACCENT_BAR
    CURSOR_ACCENT = True
    #: Marks the current branch. The row's colour already says which branch is
    #: HEAD, but colour is the only thing that does — this says it in text, the
    #: way `git branch` does. Remote branches need no mark: their names carry
    #: the remote prefix (`origin/main`), and git prefixes a local one with
    #: `heads/` when the two would otherwise read the same.
    HEAD_MARK = "*"
    keymap_namespace = "branch"
    TAB_NAME = "Branch"
    tab_key = "3"
    _SCOPES = ["local", "remote", "all"]
    _SCOPE_LABELS = {"local": "Local", "remote": "Remote", "all": "All"}

    def __init__(
        self,
        *,
        on_selection_changed: Callable | None = None,
        branch_signal: Signal[str] | None = None,
        vm: IBranchViewModel,
        id: str | None = None,
        on_toggle_preview: Callable[[], None] | None = None,
        get_git: Callable[[], GitApi],
    ) -> None:
        super().__init__(
            on_selection_changed=on_selection_changed,
            lazy_load=True,
            id=id,
            header=SectionRule("Branch"),
        )
        self._vm = vm
        self._on_toggle_preview = on_toggle_preview
        self._branch_signal = branch_signal
        self._get_git = get_git
        self.branches: list[Branch] = []
        #: What the panel shows when it has no rows; a failed load swaps in its
        #: own message and a later success must put this back.
        self._empty_state_default = self.empty_state
        self._max_right_w = 0
        self._scope_idx: int = 0
        self._rename_branch_name: str = ""
        self._rename_input = InputLine(
            prompt="Rename branch: ",
            on_submit=self._on_rename_submit,
            on_cancel=dismiss_sheet,
            allow_newline=False,
        )
        self._new_branch_input = InputLine(
            prompt="New branch: ",
            on_submit=self._on_new_branch_submit,
            on_cancel=dismiss_sheet,
            allow_newline=False,
        )
        self._alert_dialog = AlertDialog(on_result=lambda _: None)
        self._vm_unsubs: list[Callable[[], None]] = []

    def mount(self) -> None:
        super().mount()
        self._bind_vm_signals()
        # Branches arrive asynchronously via vm.items; show the skeleton until
        # they do, rather than an empty list that reads as "no branches".
        self.loading = True
        # The mark describes the load that is about to run, not the one before
        # this panel was unmounted.
        self._header.set_status(None)
        self._vm.refresh()

    def unmount(self) -> None:
        super().unmount()
        self._unbind_vm_signals()

    def set_vm(self, vm: IBranchViewModel) -> None:
        """Retarget this panel to a new Branch ViewModel (repo session switch).

        Session owns VM lifetime; this only rebinds signals and reloads.
        """
        self._unbind_vm_signals()
        self._vm = vm
        if self.is_mounted():
            self._bind_vm_signals()
            self._vm.refresh()

    def _unbind_vm_signals(self) -> None:
        """Drop subscriptions to the current ViewModel (if any)."""
        for unsub in self._vm_unsubs:
            unsub()
        self._vm_unsubs.clear()

    def _bind_vm_signals(self) -> None:
        """Bind vm.items and vm.load_error; safe to call multiple times."""
        if not self._vm_unsubs:
            self._vm_unsubs.append(
                bind_signals(
                    self,
                    self._vm.items,
                    self._vm.load_error,
                    callback=self._on_items_changed,
                )
            )

    def _on_items_changed(self) -> None:
        if not self.is_mounted():
            return
        self.loading = False
        error = self._vm.load_error.value
        self._show_load_failure(error)
        if error is not None:
            return
        branches = self._vm.items.value
        self.branches = branches
        self._recompute_meta_width()
        if not branches:
            scope = self._SCOPES[self._scope_idx]
            self.set_content([f"No {scope} branches found."])
            self._notify_change()
            return
        lines = [self._format_branch(b) for b in branches]
        self.set_content(lines)
        self._notify_change()

    def _show_load_failure(self, error: BaseException | None) -> None:
        """Wear the failure in the header, or take the mark off again.

        A failed load never reaches this panel through ``items``, so without
        the mark the panel goes on claiming it is loading (nothing loaded yet)
        or shows rows that are quietly out of date -- and the toast that said
        so is gone in three seconds.
        """
        self._header.set_status(LOAD_FAILED_MARK if error is not None else None)
        if error is None:
            self.empty_state = self._empty_state_default
        elif not self.branches:
            # Nothing older to keep, so say what happened rather than show a
            # skeleton that would never end.
            self.empty_state = load_failed_segments(error)
            self.set_content([])
        else:
            self.empty_state = self._empty_state_default

    def _recompute_meta_width(self) -> None:
        """Measure the widest metadata block, to give every row a common edge.

        A right-anchored block sits at ``w - block_width``, so rows whose
        tracking counts differ would start theirs at different columns and the
        date would shift under them. Padding each row's block to this width
        lines their left edges up. Colours do not affect width, so measuring
        with the presentation-independent path is enough.
        """
        self._max_right_w = max(
            (
                sum(wcswidth(seg.text) for seg in self._right_segments(branch))
                for branch in self.branches
            ),
            default=0,
        )

    def _handle_result(self, result: ActionResult) -> None:
        if result.success:
            show_badge(result.message, duration=1.0, kind=FeedbackKind.SUCCESS)
        else:
            show_toast(result.message, duration=2.0, kind=FeedbackKind.ERROR)
        if result.should_refresh:
            self._vm.refresh()

    def get_help_title(self) -> str:
        return "Branch"

    def get_inspector_snapshot(self) -> BranchSnapshot | None:
        """Return a frozen snapshot for the selected branch."""
        return self._vm.get_inspector_snapshot(self.curr_no)

    def _format_branch(self, branch: Branch) -> str:
        """Format a branch for display."""
        name = branch.name
        if name.startswith("remotes/"):
            name = name[len("remotes/") :]
        return name

    @bind_action("next", "j", "down", desc="Navigate branch list", tip="Navigate")
    def next(self, step: int = 1) -> None:
        super().next(step)

    @bind_action("previous", "k", "up", desc="Navigate branch list", tip="Navigate")
    def previous(self, step: int = 1) -> None:
        super().previous(step)

    @bind_action("show_log", "enter", desc="Show commits (no checkout)")
    def show_log(self) -> None:
        """Open the Commit panel on this branch's log without checkout."""
        if not self.branches:
            return
        self.emit(
            EventType("action_requested"),
            cmd="show-log",
            ref=self.branches[self.curr_no].name,
        )

    def _log_graph_preview_panel(self):
        """Return the registered log-graph preview, or None when unregistered."""
        from .app_log_graph_preview import LogGraphPreview

        try:
            return by_id("log_graph_preview", LogGraphPreview)
        except (RuntimeError, TypeError):
            return None

    @bind_action(
        "preview_down",
        "J",
        desc="Scroll log graph preview down",
        tip="Preview Navigate",
    )
    def _scroll_preview_down(self) -> None:
        preview = self._log_graph_preview_panel()
        if preview is not None and preview.is_mounted():
            preview.scroll_down(preview.SCROLL_PAGE_SIZE)

    @bind_action(
        "preview_up",
        "K",
        desc="Scroll log graph preview up",
        tip="Preview Navigate",
    )
    def _scroll_preview_up(self) -> None:
        preview = self._log_graph_preview_panel()
        if preview is not None and preview.is_mounted():
            preview.scroll_up(preview.SCROLL_PAGE_SIZE)

    @bind_action("checkout", "c", desc="Checkout selected branch", tip="Checkout")
    def checkout(self) -> None:
        from .app_bisect import guard_bisect_active

        if not self.branches:
            return
        local_branch = self.branches[self.curr_no]
        if local_branch.is_head:
            show_toast(
                "Already on this branch.", duration=1.5, kind=FeedbackKind.WARNING
            )
            return
        if local_branch.is_remote:
            show_toast(
                "Cannot checkout remote branch directly.",
                duration=1.5,
                kind=FeedbackKind.WARNING,
            )
            return
        if guard_bisect_active(self._get_git()):
            return
        # Capture the index now: the worker must check out the branch the user
        # chose, not wherever the cursor drifted to while it ran.
        index = self.curr_no
        run_with_spinner(
            lambda: self._vm.checkout(index),
            lambda result: self._after_checkout(result, local_branch.name),
            label=f"Checking out {local_branch.name}",
        )

    def _after_checkout(self, result, name: str) -> None:
        """Apply a finished checkout on the main thread."""
        self._handle_result(result)
        if not result.success:
            return
        if self._branch_signal is not None:
            self._branch_signal.set(name)
        self.emit(EventType("action_requested"), cmd="follow-head", ref=name)

    @bind_action(
        "new_branch", "n", desc="Create new branch from current HEAD", tip="New"
    )
    def new_branch(self) -> None:
        self._show_new_branch_sheet()

    @bind_action(
        "merge",
        "m",
        desc="Merge current branch into selected (requires clean worktree; may conflict)",
        tip="Merge",
    )
    def merge(self) -> None:
        self._trigger_merge()

    @bind_action("create_pull_request", "p", desc="Create pull request page in browser")
    def create_pull_request(self) -> None:
        """Open the hosting provider create-PR URL for the selected branch."""
        if not self.branches:
            return
        branch = self.branches[self.curr_no]
        from pigit.git.hosting import (
            RemoteParseError,
            UnsupportedHostingError,
            build_create_pr_url,
            head_branch_for_pr,
        )

        remote_url = self._vm.get_remote_url()
        if not remote_url:
            show_toast("No remote URL found.", duration=2.0, kind=FeedbackKind.WARNING)
            return

        head = head_branch_for_pr(name=branch.name, is_remote=branch.is_remote)
        try:
            url = build_create_pr_url(remote_url=remote_url, head_branch=head)
        except UnsupportedHostingError as exc:
            show_toast(str(exc), duration=2.5, kind=FeedbackKind.WARNING)
            return
        except (RemoteParseError, ValueError) as exc:
            show_toast(str(exc), duration=2.5, kind=FeedbackKind.ERROR)
            return

        try:
            import webbrowser

            webbrowser.open(url)
        except Exception as exc:
            show_toast(
                f"Failed to open browser: {exc}", duration=2.5, kind=FeedbackKind.ERROR
            )
            return

        show_toast(f"Opened PR page for {head}", duration=1.5, kind=FeedbackKind.INFO)

    @bind_action(
        "scope",
        "ctrl f",
        desc=lambda self: f"Scope ({self._SCOPE_LABELS[self._SCOPES[self._scope_idx]]})",
    )
    def toggle_scope(self) -> None:
        """Cycle branch scope: local -> remote -> all -> local."""
        self._scope_idx = (self._scope_idx + 1) % len(self._SCOPES)
        scope = self._SCOPES[self._scope_idx]
        label = self._SCOPE_LABELS[scope]
        show_toast(f"Branch scope: {label}", duration=2.0, kind=FeedbackKind.INFO)
        self.curr_no = 0
        self._r_start = 0
        self._vm.set_scope(scope)
        self._vm.refresh()

    @bind_action("toggle_preview", "ctrl p", desc="Toggle log graph preview")
    def toggle_preview(self) -> None:
        """Show or hide the Branch log-graph preview on a large screen."""
        if self._on_toggle_preview is not None:
            self._on_toggle_preview()

    @bind_action("rename", "R", desc="Rename selected branch", tip="Rename")
    def rename(self) -> None:
        if not self.branches:
            return
        branch = self.branches[self.curr_no]
        if branch.is_remote:
            show_toast(
                "Cannot rename remote branch.", duration=1.5, kind=FeedbackKind.WARNING
            )
            return
        self._show_rename_sheet(branch.name)

    @bind_action(
        "delete",
        "d",
        desc="Delete selected branch (fails if unmerged unless forced)",
        tip="Delete",
    )
    def delete(self) -> None:
        self._trigger_delete()

    @bind_action(
        "rebase",
        "r",
        desc="Interactive rebase onto selected branch (rewrites history)",
        tip="Rebase",
    )
    def rebase(self) -> None:
        self._trigger_rebase()

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
        sub_row: int = 0,
    ) -> tuple[
        list[Segment],
        list[Segment] | None,
        list[Segment],
    ]:
        """Return row description: [HEAD mark][branch name][tracking, date]."""
        if idx >= len(self.branches):
            return ([], None, [])
        branch = self.branches[idx]
        if branch.is_remote:
            name_fg = THEME.fg_remote_branch
        elif branch.is_head:
            name_fg = THEME.fg_local_branch
        else:
            name_fg = self.presentation_fg("primary")
        cursor_flags = palette.STYLE_BOLD if is_cursor else 0
        # The mark is status, not part of the name: fusing them moved the name
        # column with the mark, and put a flexible string in the fixed prefix.
        left = status_lane(
            [
                Segment(
                    self.HEAD_MARK if branch.is_head else " ",
                    fg=name_fg,
                    style_flags=cursor_flags,
                )
            ],
            pad_fg=self.presentation_fg("primary"),
        )
        main = [
            Segment(
                self.content[idx],
                fg=name_fg,
                style_flags=cursor_flags,
            )
        ]

        right = self._right_segments(branch)
        if right and self._max_right_w:
            # Pad to the widest row's block so the tracking counts and the date
            # start at the same column on every row, not just end there.
            right = pad_to_width(
                right,
                self._max_right_w,
                pad_fg=self.presentation_fg("muted"),
                at_front=True,
            )

        return left, main, right

    def _right_segments(self, branch) -> list[Segment]:
        """The metadata column: upstream, tracking counts, then the date."""
        right: list[Segment] = []
        if not branch.is_remote:
            if branch.upstream_name:
                right.append(
                    Segment(branch.upstream_name, fg=self.presentation_fg("muted"))
                )
            ahead = branch.ahead if branch.ahead != "?" else ""
            behind = branch.behind if branch.behind != "?" else ""
            if ahead:
                if right:
                    right.append(Segment(" ", fg=self.presentation_fg("muted")))
                right.append(Segment(f"\u2191{ahead}", fg=THEME.fg_success))
            if behind:
                if right:
                    right.append(Segment(" ", fg=self.presentation_fg("muted")))
                right.append(Segment(f"\u2193{behind}", fg=THEME.fg_warning))

        # Deliberately outside the block above: remote branches have no
        # upstream line to share, but they are sorted by this same date, so
        # they need it shown at least as much as local ones do.
        if branch.committed_at:
            if right:
                # Two spaces, like the Commit panel's meta column: the date is
                # its own column, not a continuation of the tracking counts.
                right.append(Segment("  ", fg=self.presentation_fg("muted")))
            right.append(
                Segment(
                    relative_time(branch.committed_at),
                    fg=self.presentation_fg("muted"),
                )
            )
        return right

    def _trigger_delete(self) -> None:
        """Validate constraints and show confirmation before deleting a branch."""
        if not self.branches:
            return
        branch = self.branches[self.curr_no]
        if branch.is_remote:
            show_toast(
                "Cannot delete remote branch", duration=2.0, kind=FeedbackKind.WARNING
            )
            return
        if branch.is_head:
            show_toast(
                "Cannot delete current branch", duration=1.5, kind=FeedbackKind.WARNING
            )
            return
        text = f"Delete branch '{branch.name}' ?"

        def on_result(confirmed: bool) -> None:
            if not confirmed:
                return
            result = self._vm.delete_branch(self.curr_no)
            self._handle_result(result)

        self._alert_dialog.alert(text, on_result, kind=FeedbackKind.ERROR)

    def _trigger_merge(self) -> None:
        """Validate constraints and emit merge request via callback."""
        if not self.branches:
            return
        branch = self.branches[self.curr_no]
        if branch.is_remote:
            show_toast(
                "Cannot merge into remote branch",
                duration=2.0,
                kind=FeedbackKind.WARNING,
            )
            return
        if branch.is_head:
            show_toast(
                "Already on this branch", duration=1.5, kind=FeedbackKind.WARNING
            )
            return
        ok, msg = self._vm.can_merge()
        if not ok:
            show_toast(msg, duration=2.0, kind=FeedbackKind.WARNING)
            return
        source = self._vm.current_branch()
        target = branch.name
        self.emit(
            EventType("action_requested"),
            cmd="merge",
            source=source,
            target=target,
        )

    def _trigger_rebase(self) -> None:
        """Validate and emit an interactive-rebase request for the selected branch."""
        if not self.branches:
            return
        branch = self.branches[self.curr_no]
        if branch.is_head:
            show_toast(
                "Already on this branch", duration=1.5, kind=FeedbackKind.WARNING
            )
            return
        ok, msg = self._vm.can_rebase()
        if not ok:
            show_toast(msg, duration=2.0, kind=FeedbackKind.WARNING)
            return
        self.emit(EventType("action_requested"), cmd="rebase", target=branch.name)

    def _show_new_branch_sheet(self) -> None:
        self._new_branch_input.clear()
        show_sheet(self._new_branch_input, height=3, show_edge_rule=False)

    def _on_new_branch_submit(self, name: str) -> None:
        name = name.strip()
        if not name:
            dismiss_sheet()
            return
        # `git checkout -b` rewrites the worktree like any other checkout.
        # The sheet stays open until it succeeds, so a rejected name can be
        # corrected without retyping it.
        run_with_spinner(
            lambda: self._vm.create_branch(name),
            lambda result: self._after_create_branch(result, name),
            label=f"Creating {name}",
        )

    def _after_create_branch(self, result, name: str) -> None:
        """Apply a finished branch creation on the main thread."""
        self._handle_result(result)
        if not result.success:
            return
        dismiss_sheet()
        if self._branch_signal is not None:
            self._branch_signal.set(name)
        # HEAD moved to the new branch (git checkout -b).
        self.emit(EventType("action_requested"), cmd="follow-head", ref=name)

    def _show_rename_sheet(self, branch_name: str) -> None:
        self._rename_branch_name = branch_name
        self._rename_input.set_value(branch_name)
        show_sheet(self._rename_input, height=3, show_edge_rule=False)

    def _on_rename_submit(self, new_name: str) -> None:
        new_name = new_name.strip()
        if not new_name or new_name == self._rename_branch_name:
            dismiss_sheet()
            return
        idx = self.curr_no
        result = self._vm.rename_branch(idx, new_name)
        self._handle_result(result)
        if result.success:
            dismiss_sheet()
            if self._branch_signal is not None:
                if self._branch_signal.value == self._rename_branch_name:
                    self._branch_signal.set(new_name)
                    # Renaming the current branch moves the HEAD ref name.
                    self.emit(
                        EventType("action_requested"),
                        cmd="follow-head",
                        ref=new_name,
                    )
