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
from pigit.termui.widgets import AlertDialog, InputLine, ItemList
from pigit.termui.reactive import Signal

from .app_types import BranchInfo
from .app_theme import THEME
from .viewmodels.branch import IBranchViewModel
from .viewmodels.base import ActionResult

if TYPE_CHECKING:
    from .git.model import Branch


class BranchPanel(ItemList):
    """Branch panel with ahead/behind display and current branch highlighting."""

    CURSOR = "\u25cf"
    keymap_namespace = "branch"
    _SCOPES = ["local", "remote", "all"]
    _SCOPE_LABELS = {"local": "Local", "remote": "Remote", "all": "All"}

    def __init__(
        self,
        *,
        on_selection_changed: Callable | None = None,
        branch_signal: Signal[str] | None = None,
        vm: IBranchViewModel,
        id: str | None = None,
    ) -> None:
        super().__init__(
            on_selection_changed=on_selection_changed,
            lazy_load=True,
            id=id,
        )
        self._vm = vm
        self._branch_signal = branch_signal
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
        self._vm_unsubs.append(
            bind_signals(self, vm.items, callback=self._on_items_changed)
        )

    def activate(self) -> None:
        super().activate()
        self._vm.refresh()

    def _on_items_changed(self) -> None:
        branches = self._vm.items.value
        if not self.is_activated():
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

    def deactivate(self) -> None:
        super().deactivate()
        for unsub in self._vm_unsubs:
            unsub()
        self._vm_unsubs.clear()
        self._vm.dispose()

    def _handle_result(self, result: ActionResult) -> None:
        if result.success:
            show_badge(result.message, duration=1.0, kind=FeedbackKind.SUCCESS)
        else:
            show_toast(result.message, duration=2.0, kind=FeedbackKind.ERROR)
        if result.should_refresh:
            self._vm.refresh()

    def get_help_title(self) -> str:
        return "Branch"

    def get_inspector_data(self) -> BranchInfo | None:
        """Return inspector data for the currently selected branch."""
        return self._vm.get_inspector_data(self.curr_no)

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

    def _log_graph_preview_panel(self):
        """Return the registered log-graph preview, or raise if missing."""
        from .app_log_graph_preview import LogGraphPreview

        return by_id("log_graph_preview", LogGraphPreview)

    @bind_action(
        "preview_down",
        "J",
        desc="Scroll log graph preview down",
        tip="Preview Navigate",
    )
    def _scroll_preview_down(self) -> None:
        preview = self._log_graph_preview_panel()
        preview.scroll_down(preview.SCROLL_PAGE_SIZE)

    @bind_action(
        "preview_up",
        "K",
        desc="Scroll log graph preview up",
        tip="Preview Navigate",
    )
    def _scroll_preview_up(self) -> None:
        preview = self._log_graph_preview_panel()
        preview.scroll_up(preview.SCROLL_PAGE_SIZE)

    @bind_action("checkout", "c", desc="Checkout selected branch", tip="Checkout")
    def checkout(self) -> None:
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
        result = self._vm.checkout(self.curr_no)
        self._handle_result(result)
        if result.success and self._branch_signal is not None:
            self._branch_signal.set(local_branch.name)

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
        tip="Scope",
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
        """Return row description: [cursor][branch_name.......][↑ahead ↓behind]"""
        focused = self.is_focus_leaf
        is_head = idx < len(self.branches) and self.branches[idx].is_head
        prefix = self.CURSOR if is_cursor else " "
        if is_head:
            fg = THEME.fg_success if focused else THEME.fg_dim
        else:
            fg = THEME.fg_primary if focused else THEME.fg_dim
        left = [
            Segment(
                f"{prefix} {self.content[idx]}",
                fg=fg,
                style_flags=palette.STYLE_BOLD if is_cursor else 0,
            )
        ]

        right: list[Segment] = []
        if idx < len(self.branches):
            branch = self.branches[idx]
            if not branch.is_remote:
                if branch.upstream_name:
                    right.append(Segment(branch.upstream_name, fg=THEME.fg_muted))
                ahead = branch.ahead if branch.ahead != "?" else ""
                behind = branch.behind if branch.behind != "?" else ""
                if ahead:
                    if right:
                        right.append(Segment(" ", fg=THEME.fg_muted))
                    right.append(Segment(f"\u2191{ahead}", fg=THEME.fg_success))
                if behind:
                    if right:
                        right.append(Segment(" ", fg=THEME.fg_muted))
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

        self._alert_dialog.alert(text, on_result, destructive=True)

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
        show_sheet(self._new_branch_input, height=3)

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

    def _show_rename_sheet(self, branch_name: str) -> None:
        self._rename_branch_name = branch_name
        self._rename_input.set_value(branch_name)
        show_sheet(self._rename_input, height=3)

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
