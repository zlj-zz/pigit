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
from .app_theme import THEME
from .viewmodels.branch import IBranchViewModel
from .viewmodels.base import ActionResult

if TYPE_CHECKING:
    from pigit.git.api import GitApi
    from .git.model import Branch


class BranchPanel(OptionList):
    """Branch panel with ahead/behind display and current branch highlighting."""

    CURSOR = ACCENT_BAR
    CURSOR_ACCENT = True
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
        self._alert_dialog = AlertDialog(
            inner_width=40,
            on_result=lambda _: None,
        )
        self._vm_unsubs: list[Callable[[], None]] = []

    def mount(self) -> None:
        super().mount()
        self._bind_vm_signals()
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
        """Bind vm.items; safe to call multiple times (idempotent)."""
        if not self._vm_unsubs:
            self._vm_unsubs.append(
                bind_signals(self, self._vm.items, callback=self._on_items_changed)
            )

    def _on_items_changed(self) -> None:
        branches = self._vm.items.value
        if not self.is_mounted():
            return
        self.branches = branches
        if not branches:
            scope = self._SCOPES[self._scope_idx]
            self.set_content([f"No {scope} branches found."])
            self._notify_change()
            return
        lines = [self._format_branch(b) for b in branches]
        self.set_content(lines)
        self._notify_change()

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
        result = self._vm.checkout(self.curr_no)
        self._handle_result(result)
        if result.success and self._branch_signal is not None:
            self._branch_signal.set(local_branch.name)
        if result.success:
            self.emit(
                EventType("action_requested"),
                cmd="follow-head",
                ref=local_branch.name,
            )

    @bind_action(
        "new_branch", "n", desc="Create new branch from current HEAD", tip="New"
    )
    def new_branch(self) -> None:
        self._show_new_branch_sheet()

    @bind_action(
        "merge",
        "m",
        desc="Merge selected branch into current (requires clean worktree; may conflict)",
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
        """Return row description: [cursor][branch_name.......][↑ahead ↓behind]."""
        if idx >= len(self.branches):
            return ([], None, [])
        branch = self.branches[idx]
        if branch.is_remote:
            name_fg = THEME.fg_remote_branch
        elif branch.is_head:
            name_fg = THEME.fg_local_branch
        else:
            name_fg = self.presentation_fg("primary")
        left = [
            Segment(
                f" {self.content[idx]}",
                fg=name_fg,
                style_flags=palette.STYLE_BOLD if is_cursor else 0,
            )
        ]

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

        return left, None, right

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
        result = self._vm.create_branch(name)
        self._handle_result(result)
        if result.success:
            dismiss_sheet()
            if self._branch_signal is not None:
                self._branch_signal.set(name)
            # HEAD moved to the new branch (git checkout -b).
            self.emit(
                EventType("action_requested"),
                cmd="follow-head",
                ref=name,
            )

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
