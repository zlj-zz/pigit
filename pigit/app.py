"""
Module: pigit/app.py
Description: Git TUI panels and application entry.
Author: Zev
Date: 2026-04-17
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable

from pigit.termui import (
    EventType,
    EVT_SELECTION_CHANGED,
    FeedbackKind,
    AlertDialog,
    bind_action,
    Application,
    Component,
    ComponentRoot,
    dismiss_sheet,
    exec_external,
    ExitEventLoop,
    get_focus_manager,
    get_renderer,
    HelpPanel,
    hide_spinner,
    keys,
    Popup,
    request_render,
    resolve_presentation_leaf,
    show_badge,
    show_sheet,
    show_spinner,
    show_toast,
    ToastPosition,
    set_theme,
)
from pigit.termui.cli_output import Console
from pigit.termui.containers import Column, SplitPane, TabView
from pigit.termui.tty_io import terminal_size
from pigit.termui.widgets import Header
from pigit.termui.reactive import Signal
from .app_header_state import HeaderState
from .git.api import GitApi, GitError, RepoError
from .app_branch import BranchPanel
from .app_chrome import AppFooter
from .app_commit import CommitPanel
from .app_diff import DiffViewer
from .app_inspector import InspectorSheet
from .app_types import InspectorHost
from .app_command_palette import CommandPalette
from .app_preview import PreviewPanel
from .app_log_graph_preview import LogGraphPreview
from .app_stash import StashPanel
from .app_status import StatusPanel
from .app_theme import THEME
from .git.managed_repos import ManagedRepos
from .viewmodels.status import StatusViewModel
from .viewmodels.branch import BranchViewModel
from .viewmodels.commit import CommitViewModel
from .session_history import SessionHistory
from .config_data import AppConfig


class PigitApplication(Application):
    """Pigit TUI application entry."""

    keymap_namespace = "universal"
    min_terminal_size = (65, 10)

    def __init__(
        self,
        *,
        git_api: GitApi | None = None,
        managed_repos: ManagedRepos | None = None,
        config: AppConfig,
    ) -> None:
        super().__init__(input_takeover=True)
        set_theme(THEME)
        self._git_api = git_api or GitApi()
        self._managed_repos = managed_repos
        self._repo_path, self._repo_conf = self._git_api.confirm_repo()
        self._git = self._git_api.bind_path(self._repo_path)
        # Header state
        self._repo_name: str = ""
        self._header_state = HeaderState(THEME)
        self._branch_signal: Signal[str] = self._header_state.branch_signal
        self._header_unsub = self._header_state.bind_to_bus(self._event_bus)
        # Merge workflow state
        self._merge_state: dict | None = None
        self._alert_dialog = AlertDialog(
            inner_width=50,
            on_result=lambda _: None,
        )
        # Session history (undo stack)
        self._session_history = SessionHistory(max_items=100, max_memory_mb=50)
        # Auto-refresh
        self._config = config
        self._refresh_timer_id: int | None = None
        # ViewModels (assigned in build_root, same lifetime as panels)
        self._status_vm: StatusViewModel
        self._commit_vm: CommitViewModel
        self._branch_vm: BranchViewModel
        # Adaptive split state
        self._preview_panel: PreviewPanel | None = None
        self._log_graph_preview: LogGraphPreview | None = None
        self._is_large_screen = False
        self._diff_preview_wanted = config.diff_preview_default
        self._log_graph_wanted = config.log_graph_default
        self._preview_unsub: Callable[[], None] | None = None
        # Typed accessors for key body components (assigned in build_root)
        self._tab_view: TabView
        self._body_row: SplitPane
        self._palette: CommandPalette
        self._status_stack: Column
        self._status_panel: StatusPanel
        self._stash_panel: StashPanel
        self._branch_panel: BranchPanel
        self._commit_panel: CommitPanel
        self._diff_panel: DiffViewer

    LARGE_SCREEN_COLS = 120

    def build_root(self) -> Component:
        footer = AppFooter(theme=THEME, id="footer")
        footer.set_global_help([(";", "Palette"), ("I", "Inspector"), ("Q", "Quit")])

        self._status_vm = StatusViewModel(self._git, history=self._session_history)
        self._branch_vm = BranchViewModel(self._git, history=self._session_history)
        self._commit_vm = CommitViewModel(self._git)

        # Side previews are created at app level but only inserted into the
        # layout on large screens: Status/Stash use diff preview, Branch uses
        # the log-graph preview. At most one is in body_row at a time.
        self._preview_panel = PreviewPanel(
            id="preview",
            status_vm=self._status_vm,
        )
        self._log_graph_preview = LogGraphPreview(
            id="log_graph_preview",
            vm=self._branch_vm,
        )

        self._status_panel = StatusPanel(
            vm=self._status_vm,
            id="status_panel",
            default_view=self._config.status_view,
            on_toggle_preview=self.toggle_side_preview,
        )
        self._stash_panel = StashPanel(
            vm=self._status_vm,
            id="stash",
            on_toggle_preview=self.toggle_side_preview,
        )
        self._status_stack = Column(
            children=[self._status_panel, self._stash_panel],
            heights=["flex", 4],
            focus_index=0,
            id="status",
        )

        self._branch_panel = BranchPanel(
            vm=self._branch_vm,
            branch_signal=self._branch_signal,
            id="branch",
            on_toggle_preview=self.toggle_side_preview,
        )

        self._commit_panel = CommitPanel(
            vm=self._commit_vm,
            id="commit",
            report_default=self._config.commit_report_default,
        )
        self._diff_panel = DiffViewer(id="diff", word_diff=self._config.word_diff)
        self._tab_view = TabView(
            children=[
                self._status_stack,
                self._branch_panel,
                self._commit_panel,
                self._diff_panel,
            ],
            start="status",
            on_switch=self._on_tab_switch,
            id="tab_view",
        )

        cols, _ = terminal_size()
        self._is_large_screen = cols >= self.LARGE_SCREEN_COLS

        self._body_row = SplitPane(
            master=self._tab_view,
            breakpoint_cols=self.LARGE_SCREEN_COLS,
            id="body_row",
        )

        self._palette = CommandPalette(
            on_execute=self._on_palette_execute,
            on_dismiss=self._dismiss_palette,
            id="palette",
        )

        children = [
            Header(
                left=self._header_state.left,
                center=self._header_state.center,
                right=self._header_state.right,
                separator=True,
                sep_fg=THEME.fg_dim,
                id="header",
            ),
            self._body_row,
        ]
        heights: list = [2, "flex"]
        if self._config.show_footer:
            children.append(footer)
            heights.append(2)
        return Column(children=children, heights=heights)

    def _on_tab_switch(self, panel: Component) -> None:
        """React to TabView switching to a new panel.

        Adjusts the adaptive layout on large screens and emits
        ``selection_changed`` so bus subscribers (footer, header, preview)
        can update themselves.
        """
        if self._is_large_screen:
            cols, _ = terminal_size()
            self._apply_body_widths(cols)
        panel.emit(EVT_SELECTION_CHANGED)

    def setup_root(self, root: ComponentRoot) -> None:
        self._help_panel = HelpPanel(
            key_fg=THEME.fg_info,
        )
        self._help_panel.set_grouped_entries(self.get_help_groups())
        self._help_popup = Popup(
            self._help_panel,
            exit_key=keys.KEY_ESC,
        )

    def get_help_groups(self) -> list[tuple[str, list[tuple[str, str]]]]:
        """Aggregate full-help groups from app + panel action bindings."""
        groups: list[tuple[str, list[tuple[str, str]]]] = []
        universal = self.get_help_entries()
        if universal:
            groups.append(("Global", universal))
        for panel in (
            self._status_panel,
            self._stash_panel,
            self._branch_panel,
            self._commit_panel,
            self._diff_panel,
        ):
            entries = panel.get_help_entries()
            if entries:
                groups.append((panel.get_help_title(), entries))
        return groups

    def after_start(self):
        cols, rows = terminal_size()
        self._sync_stash_height(rows)
        if self._is_large_screen:
            self._apply_body_widths(cols)

        # Initialize header with repo info
        try:
            head = self._git.get_head() or ""
            self._repo_name = (
                os.path.basename(self._repo_path) if self._repo_path else ""
            )
            self._header_state.repo = self._repo_name
            self._header_state.branch = head
        except Exception:
            logging.warning("Failed to initialize repo info", exc_info=True)
            show_toast(
                "Failed to load repo info. Check git configuration.",
                duration=3.0,
                position=ToastPosition.BOTTOM_LEFT,
                kind=FeedbackKind.ERROR,
            )

        show_toast(
            "Welcome to Pigit! Press ? for help.",
            duration=3.0,
            position=ToastPosition.BOTTOM_LEFT,
            kind=FeedbackKind.INFO,
        )
        self._try_restore_merge_state()

        # Register auto-refresh timer
        if self._loop is not None and self._config.auto_refresh_interval > 0:
            if self._refresh_timer_id is not None:
                self._loop.remove_interval(self._refresh_timer_id)
            self._refresh_timer_id = self._loop.add_interval(
                self._config.auto_refresh_interval,
                self._refresh_active_panel,
            )

        # Initial sync: all components are activated now, so subscribers receive
        # the event and update header/footer/preview.
        if self._tab_view.active is not None:
            self._on_tab_switch(self._tab_view.active)

    def _side_preview_for_active(self) -> Component | None:
        """Return the one large-screen side panel for the current tab, or None."""
        if not self._is_large_screen:
            return None
        active = resolve_presentation_leaf(self._tab_view.active)
        if isinstance(active, (StatusPanel, StashPanel)):
            return self._preview_panel if self._diff_preview_wanted else None
        if isinstance(active, BranchPanel):
            return self._log_graph_preview if self._log_graph_wanted else None
        return None

    def _apply_body_widths(self, cols: int) -> None:
        """Update SplitPane detail and widths for the active tab."""
        active = resolve_presentation_leaf(self._tab_view.active)
        if isinstance(active, (StatusPanel, StashPanel)):
            self._body_row.set_detail(self._preview_panel)
            self._body_row.set_detail_wanted(
                self._is_large_screen and self._diff_preview_wanted
            )
        elif isinstance(active, BranchPanel):
            self._body_row.set_detail(self._log_graph_preview)
            self._body_row.set_detail_wanted(
                self._is_large_screen and self._log_graph_wanted
            )
        else:
            self._body_row.set_detail(None)
            self._body_row.set_detail_wanted(False)
        self._body_row.apply_terminal_width(cols)

    @bind_action("help", "?", desc="Toggle this help panel", tip="Help")
    def toggle_help(self):
        """Toggle help popup visibility. Rebuild groups so Commit's title tracks log_ref."""
        self._help_panel.set_grouped_entries(self.get_help_groups())
        self._help_popup.toggle()

    @bind_action("palette", ";", desc="Open command palette", tip="Palette")
    def toggle_palette(self):
        """Toggle command palette visibility."""
        if self._root is None:
            return
        if self._palette.is_active:
            self._palette.close()
        else:
            self._palette.open()
            self._root.show_sheet(self._palette, height=8)

    @bind_action("goto_status", "1", desc="Switch to Status panel", tip="Status")
    def goto_status(self):
        """Switch focus to the Status panel."""
        self._focus_destination(self._status_panel)

    @bind_action("goto_stash", "2", desc="Switch to Stash panel", tip="Stash")
    def goto_stash(self):
        """Switch focus to the Stash panel."""
        self._focus_destination(self._stash_panel)

    @bind_action("goto_branch", "3", desc="Switch to Branch tab", tip="Branch")
    def goto_branch(self):
        """Switch focus to the Branch panel."""
        self._focus_destination(self._branch_panel)

    @bind_action("goto_commit", "4", desc="Switch to Commit tab", tip="Commit")
    def goto_commit(self):
        """Switch focus to the Commit panel."""
        self._focus_destination(self._commit_panel)

    @bind_action(
        "next_panel",
        "tab",
        desc="Cycle to next panel (Status, Stash, Branch, Commit)",
    )
    def next_panel(self) -> None:
        """Cycle focus to the next panel in the Status → Stash → Branch → Commit ring."""
        self._cycle_panel(1)

    @bind_action(
        "prev_panel",
        "shift tab",
        desc="Cycle to previous panel (Status, Stash, Branch, Commit)",
    )
    def prev_panel(self) -> None:
        """Cycle focus to the previous panel in the Status → Stash → Branch → Commit ring."""
        self._cycle_panel(-1)

    def _panel_ring(self) -> tuple[Component, ...]:
        """Return the four panels that Tab/Shift+Tab cycle through, in order."""
        return (
            self._status_panel,
            self._stash_panel,
            self._branch_panel,
            self._commit_panel,
        )

    def _ring_index(self) -> int | None:
        """Index in the panel ring, or None when Diff (or unknown) is focused."""
        fm = get_focus_manager()
        leaf = fm.get_focus_leaf() if fm is not None else None
        if leaf is None:
            leaf = resolve_presentation_leaf(self._tab_view.active)
        for idx, panel in enumerate(self._panel_ring()):
            if leaf is panel:
                return idx
        return None

    def _focus_destination(self, panel: Component) -> None:
        """Move TabView + Status/Stash column focus to *panel*."""
        if panel is self._status_panel:
            self._tab_view.route_to("status")
            self._status_stack.set_focus_index(0)
            return
        if panel is self._stash_panel:
            self._tab_view.route_to("status")
            self._status_stack.set_focus_index(1)
            return
        if panel is self._branch_panel:
            self._tab_view.route_to("branch")
            return
        if panel is self._commit_panel:
            self._tab_view.route_to("commit")

    def _cycle_panel(self, step: int) -> None:
        """Move focus ``step`` positions around the panel ring.

        No-op when the current focus is outside the ring (e.g. Diff view).
        """
        idx = self._ring_index()
        if idx is None:
            return
        ring = self._panel_ring()
        self._focus_destination(ring[(idx + step) % len(ring)])

    @bind_action("undo", "u", desc="Reverse last action", tip="Undo")
    def reverse_last_action(self) -> None:
        """Reverse the most recent session action."""
        recent = self._session_history.peek(1)
        was_checkout = bool(
            recent
            and any(cmd.op_type == "checkout_branch" for cmd in recent[0].commands)
        )
        result = self._session_history.reverse(self._git)
        if result.success:
            show_badge(result.message, duration=1.5, kind=FeedbackKind.SUCCESS)
            if was_checkout:
                # Undoing a checkout moved HEAD; point the commit list at it.
                self._on_follow_head(self._git.get_head() or "HEAD")
            self._refresh_active_panel()
        else:
            show_toast(result.message, duration=2.0, kind=FeedbackKind.ERROR)

    @bind_action("recent", "U", desc="Open recent actions sheet", tip="Recent")
    def open_recent_actions(self) -> None:
        """Open the RecentActionsPanel sheet overlay."""
        from .app_recent_actions import RecentActionsPanel

        def _on_done() -> None:
            dismiss_sheet()
            self._refresh_active_panel()

        panel = RecentActionsPanel(self._session_history, self._git, on_done=_on_done)
        rows = terminal_size()[1]
        show_sheet(panel, height=min(12, rows // 3), show_border=True)
        panel.activate()

    def toggle_side_preview(self) -> None:
        """Toggle the side preview that belongs to the focused panel."""
        cols, _ = terminal_size()
        if cols < self.LARGE_SCREEN_COLS:
            show_toast(
                f"Need at least {self.LARGE_SCREEN_COLS} columns for preview",
                duration=2.0,
                kind=FeedbackKind.WARNING,
            )
            return
        active = resolve_presentation_leaf(self._tab_view.active)
        if isinstance(active, (StatusPanel, StashPanel)):
            self._diff_preview_wanted = not self._diff_preview_wanted
            showing = self._diff_preview_wanted
            hidden = self._preview_panel
        elif isinstance(active, BranchPanel):
            self._log_graph_wanted = not self._log_graph_wanted
            showing = self._log_graph_wanted
            hidden = self._log_graph_preview
        else:
            return
        self._apply_body_widths(cols)
        if showing:
            if self._tab_view.active is not None:
                self._tab_view.active.emit(EVT_SELECTION_CHANGED)
        elif hidden is not None:
            hidden.clear()
        renderer = get_renderer()
        if renderer is not None:
            renderer.clear_cache()
        request_render()

    @bind_action("inspector", "I", desc="Inspect selection", tip="Inspector")
    def open_inspector(self) -> None:
        """Open a frozen top-edge snapshot of the current selection."""
        active = resolve_presentation_leaf(self._tab_view.active)
        if not isinstance(active, InspectorHost):
            show_toast(
                "No inspector for this view",
                duration=1.5,
                kind=FeedbackKind.INFO,
            )
            return
        snapshot = active.get_inspector_snapshot()
        if snapshot is None:
            show_toast(
                "Nothing to inspect",
                duration=1.5,
                kind=FeedbackKind.INFO,
            )
            return
        lines = InspectorSheet.format(snapshot)
        _, rows = terminal_size()
        height = InspectorSheet.sheet_height(lines, rows, border=1)
        sheet = InspectorSheet(lines)
        show_sheet(sheet, height=height, show_border=True, edge="top", bg=None)
        sheet.activate()

    @bind_action("quit", "Q", "q", desc="Quit Pigit", tip="Quit")
    def quit(self, *, exit_code: int = 0, result_message: str | None = None):
        raise ExitEventLoop("Quit", exit_code=exit_code, result_message=result_message)

    def _dismiss_palette(self) -> None:
        """Dismiss the palette sheet from the root."""
        if self._root is not None:
            self._root.dismiss_sheet()

    def _sync_stash_height(self, rows: int) -> None:
        """Set StashPanel height to 25% of rows, capped at 10, min 3."""
        self._status_stack.set_heights(["flex", min(max(3, int(rows * 0.25)), 10)])

    def resize(self, size: tuple[int, int]) -> None:
        """Recompute layout widths and stash height on terminal resize.

        The event loop resizes the component tree after this returns.
        """
        cols, rows = size
        was_large = self._is_large_screen
        self._is_large_screen = cols >= self.LARGE_SCREEN_COLS
        self._sync_stash_height(rows)
        self._apply_body_widths(cols)
        if was_large and not self._is_large_screen:
            for panel in (self._preview_panel, self._log_graph_preview):
                if panel is not None:
                    panel.clear()
        if not was_large and self._is_large_screen:
            if self._tab_view.active is not None:
                self._tab_view.active.emit(EVT_SELECTION_CHANGED)

    def _refresh_active_panel(self) -> None:
        """Auto-refresh callback: refresh the currently active panel's VM.

        Skips when an overlay is open (user is in modal/sheet).
        Does NOT call request_render(); vm.refresh() uses AsyncTask,
        and Signal subscribers trigger rendering when data arrives.
        """
        active = resolve_presentation_leaf(self._tab_view.active)
        if active is None:
            return
        # Skip refresh when an overlay is open
        if self._root is not None and self._root.has_overlay_open():
            return
        # Prefer panel-level refresh (e.g. StashPanel.refresh reloads stashes)
        if hasattr(active, "refresh") and callable(getattr(active, "refresh")):
            active.refresh()
        else:
            vm = getattr(active, "_vm", None)
            if vm is not None and hasattr(vm, "refresh"):
                vm.refresh()

    def _on_rebase_request(self, target: str) -> None:
        """Open the interactive-rebase todo panel for ``target``."""
        from .app_rebase import RebasePanel

        def _on_done() -> None:
            dismiss_sheet()
            self._refresh_active_panel()

        panel = RebasePanel(self._git, target, on_done=_on_done)
        rows = terminal_size()[1]
        show_sheet(panel, height=min(20, rows - 4), show_border=True)
        panel.activate()

    def on_event(self, action: EventType, **data) -> bool:
        """Bridge bubbled events to the framework bus; enrich cross-cutting events.

        Application-level handlers (e.g. merge workflow) run after enrichment.
        Header, footer, and preview updates are handled by their own
        bus subscribers.
        """
        if action in (EventType("mode_changed"), EVT_SELECTION_CHANGED):
            data.setdefault("active", self._resolve_active_panel())
        if action is EventType("action_requested") and data.get("cmd") == "merge":
            self._on_merge_request(data["source"], data["target"])
            return True
        if action is EventType("action_requested") and data.get("cmd") == "rebase":
            self._on_rebase_request(data["target"])
            return True
        if action is EventType("action_requested") and data.get("cmd") == "cherry-pick":
            self._on_cherry_pick(data["sha"], bool(data.get("is_merge")))
            return True
        if action is EventType("action_requested") and data.get("cmd") == "show-log":
            self._on_show_log(data["ref"])
            return True
        if action is EventType("action_requested") and data.get("cmd") == "follow-head":
            self._on_follow_head(data["ref"])
            return True
        return self._event_bus.publish(action, **data)

    def _resolve_active_panel(self) -> Component | None:
        """Return the currently presented active panel, or None."""
        if self._root is None:
            return None
        return resolve_presentation_leaf(self._tab_view.active)

    def _pin_log_ref(self, ref: str, *, announce: bool = True) -> None:
        """Pin the Commit log to ``ref``; announce unless it is the checkout."""
        self._commit_vm.set_log_ref(ref)
        if announce and not self._commit_vm.viewing_checkout_log():
            show_toast(f"Showing log: {ref}", duration=1.5, kind=FeedbackKind.INFO)

    def _on_show_log(self, ref: str) -> None:
        """Pin Commit log to ``ref`` and open the Commit tab."""
        self._pin_log_ref(ref)
        if self._tab_view.route_to("commit") is None:
            # Already on the Commit tab; refresh the title directly.
            self._commit_panel._publish_tab_title()

    def _on_follow_head(self, ref: str) -> None:
        """After a HEAD move, point the commit list at the new checkout."""
        reset = self._commit_vm.follow_head(ref)
        if reset:
            show_toast(
                f"Log pin reset to {ref}",
                duration=2.0,
                kind=FeedbackKind.WARNING,
            )
        self._commit_panel._publish_tab_title()

    def _on_palette_execute(self, cmd: str) -> None:
        """Handle command palette execution."""
        lower = cmd.lower()
        if lower == "quit":
            self.quit()
        elif self._tab_view.route_to(lower) is not None:
            return
        if lower in ("pull", "push", "fetch"):
            self._run_git_action(lower)
            return
        if lower == "continue-merge":
            self._continue_merge()
            return
        if lower in ("rebase-continue", "rebase-abort", "rebase-skip"):
            self._run_rebase_control(lower)
            return
        if lower in (
            "cherry-pick-continue",
            "cherry-pick-abort",
            "cherry-pick-skip",
        ):
            self._run_cherry_pick_control(lower)
            return

    def _run_git_action(self, action: str) -> None:
        """Run a git action via exec_external and show result toast."""
        try:
            result = exec_external(["git", action], cwd=self._repo_path)
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
        except Exception as e:
            show_toast(
                f"Git {action} error: {e}", duration=3.0, kind=FeedbackKind.ERROR
            )

    def _run_rebase_control(self, action: str) -> None:
        """Run a rebase control flag (--continue/--abort/--skip)."""
        flag = action[len("rebase-") :]
        if flag == "abort":

            def on_confirm(confirmed: bool) -> None:
                if confirmed:
                    self._do_rebase_control(flag)

            self._alert_dialog.alert(
                "Abort rebase? All progress will be lost.",
                on_confirm,
                destructive=True,
            )
            return
        self._do_rebase_control(flag)

    def _refresh_git_vms(self) -> None:
        """Refresh Status, Branch, and Commit VMs (safe while a palette overlay is open)."""
        self._status_vm.refresh()
        self._branch_vm.refresh()
        self._commit_vm.refresh()

    _SEQUENCER_PAUSED = {
        "rebase": "Rebase paused. Resolve/edit, then ';' → rebase-continue/abort/skip",
        "cherry-pick": "Cherry-pick paused. Resolve, then ';' → cherry-pick-continue/abort/skip",
        "revert": "Revert paused. Resolve, then ';' → cherry-pick-continue/abort/skip",
    }

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
        still = self._git.sequencer_in_progress()
        if result.returncode == 0:
            if still is not None:
                show_toast(
                    self._SEQUENCER_PAUSED.get(still, f"{still} paused"),
                    duration=3.0,
                    kind=FeedbackKind.WARNING,
                )
            else:
                show_toast(done_msg, duration=1.5, kind=FeedbackKind.SUCCESS)
            self._refresh_git_vms()
            return
        show_toast(failed_msg, duration=2.0, kind=FeedbackKind.ERROR)

    def _do_rebase_control(self, flag: str) -> None:
        """Execute ``git rebase --<flag>`` via exec_external and refresh panels."""
        try:
            result = exec_external(["git", "rebase", f"--{flag}"], cwd=self._repo_path)
        except Exception as e:
            show_toast(
                f"Rebase {flag} error: {e}", duration=3.0, kind=FeedbackKind.ERROR
            )
            return
        self._after_external_git(
            result,
            flag=flag,
            done_msg=f"Rebase {flag} completed",
            failed_msg=f"Rebase {flag} failed",
        )

    def _run_cherry_pick_control(self, action: str) -> None:
        """Run a cherry-pick control flag (--continue/--abort/--skip)."""
        flag = action[len("cherry-pick-") :]
        if flag == "abort":

            def on_confirm(confirmed: bool) -> None:
                if confirmed:
                    self._do_cherry_pick_control(flag)

            self._alert_dialog.alert(
                "Abort cherry-pick? All progress will be lost.",
                on_confirm,
                destructive=True,
            )
            return
        self._do_cherry_pick_control(flag)

    def _do_cherry_pick_control(self, flag: str) -> None:
        """Execute ``git cherry-pick --<flag>`` via exec_external."""
        argv = ["git", "cherry-pick", f"--{flag}"]
        if flag == "continue":
            argv.append("--no-edit")
        try:
            result = exec_external(argv, cwd=self._repo_path)
        except Exception as e:
            show_toast(
                f"Cherry-pick {flag} error: {e}",
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

    def _on_cherry_pick(self, sha: str, is_merge: bool) -> None:
        """Guard, confirm, then copy ``sha`` onto HEAD via exec_external."""
        try:
            kind = self._git.sequencer_in_progress()
            if kind is not None:
                show_toast(
                    f"A {kind} is already in progress",
                    duration=2.0,
                    kind=FeedbackKind.WARNING,
                )
                return
            if sha == self._git.resolve_head_sha():
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
        except (GitError, RepoError) as e:
            show_toast(str(e), duration=2.0, kind=FeedbackKind.ERROR)
            return

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                self._exec_cherry_pick(sha)

        self._alert_dialog.alert(
            f"Cherry-pick {sha[:7]} onto current HEAD?",
            on_confirm,
        )

    def _exec_cherry_pick(self, sha: str) -> None:
        """Run ``git cherry-pick`` after the user confirmed."""
        try:
            result = exec_external(["git", "cherry-pick", sha], cwd=self._repo_path)
        except Exception as e:
            show_toast(f"Cherry-pick error: {e}", duration=3.0, kind=FeedbackKind.ERROR)
            return
        self._finish_cherry_pick(result, sha)

    def _finish_cherry_pick(self, result, sha: str) -> None:
        """Toast or badge the outcome of a just-run cherry-pick."""
        try:
            kind = self._git.sequencer_in_progress()
            if result.returncode == 0:
                show_badge(f"Cherry-picked {sha[:7]}")
                self._refresh_git_vms()
                return
            if kind == "cherry-pick":
                if self._git.has_unmerged_paths():
                    show_toast(
                        "Conflict! Resolve in Status, then ';' → cherry-pick-continue/abort",
                        duration=3.0,
                        kind=FeedbackKind.WARNING,
                    )
                    self._tab_view.route_to("status")
                else:
                    show_toast(
                        "Cherry-pick is empty. ';' → cherry-pick-skip or cherry-pick-abort",
                        duration=3.0,
                        kind=FeedbackKind.WARNING,
                    )
                return
        except (GitError, RepoError) as e:
            show_toast(str(e), duration=2.0, kind=FeedbackKind.ERROR)
            return
        show_toast("Cherry-pick failed", duration=2.0, kind=FeedbackKind.ERROR)
        self._refresh_git_vms()

    def _merge_state_path(self) -> str:
        """Return the path to the persistent merge state file."""
        git_dir = self._git.get_git_dir()
        return os.path.join(git_dir, "pigit_merge_state")

    def _save_merge_state(self, source: str, target: str) -> None:
        try:
            with open(self._merge_state_path(), "w") as f:
                json.dump({"source": source, "target": target}, f)
        except Exception:
            pass

    def _load_merge_state(self) -> dict | None:
        try:
            with open(self._merge_state_path()) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _clear_merge_state(self) -> None:
        try:
            os.remove(self._merge_state_path())
        except FileNotFoundError:
            pass

    def _try_restore_merge_state(self) -> None:
        """On startup: recover pending merge state if merge is still in progress.

        Swallows GitError (e.g. not a git repo) \u2014 merge state restoration is
        best-effort and should never prevent the TUI from starting.
        """
        try:
            state = self._load_merge_state()
        except GitError:
            return
        if state is None:
            return
        if self._git.is_merge_in_progress():
            self._merge_state = state
            self._header_state.merge_target = state.get("target", "")
            show_toast(
                f"Resume merge: {state['source']} \u2192 {state['target']} (continue-merge)",
                duration=3.0,
                kind=FeedbackKind.INFO,
            )
        else:
            self._clear_merge_state()
            self._header_state.merge_target = ""

    def _on_merge_request(self, source: str, target: str) -> None:
        """Callback from BranchPanel: confirm then execute merge workflow."""
        kind = self._git.sequencer_in_progress()
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
                self._do_merge_workflow(source, target)
            except GitError as e:
                hide_spinner()
                err_msg = str(e).lower()
                if "conflict" in err_msg:
                    self._merge_state = {"source": source, "target": target}
                    self._header_state.merge_target = target
                    self._save_merge_state(source, target)
                    show_toast(
                        "Conflict! Resolve in Status, then continue-merge",
                        duration=3.0,
                        kind=FeedbackKind.WARNING,
                    )
                    self._tab_view.route_to("status")
                    return
                show_toast(f"Merge failed: {e}", duration=3.0, kind=FeedbackKind.ERROR)
                return
            except Exception:
                hide_spinner()
                logging.exception("Merge workflow failed with unexpected error")
                return
            self._confirm_push_and_finish(target, source)

        self._alert_dialog.alert(f"Merge {source} into {target}?", on_confirm)

    def _do_merge_workflow(self, source: str, target: str) -> None:
        """Atomically: checkout target \u2192 pull \u2192 merge source.

        On any step failure, best-effort checkout back to source then raise.
        """
        steps = [
            (f"Checking out {target}", lambda: self._git.checkout_branch(target)),
            (f"Pulling {target}", lambda: self._git.pull()),
            (f"Merging {source}", lambda: self._git.merge(source)),
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

    def _try_checkout_back(self, source: str) -> None:
        """Best-effort checkout back to source branch on failure."""
        try:
            self._git.checkout_branch(source)
        except GitError:
            pass

    def _confirm_push_and_finish(self, target: str, source: str) -> None:
        """Alert confirm push, then checkout back to source branch."""

        def on_push_confirmed(confirmed: bool) -> None:
            if confirmed:
                show_spinner(f"Pushing {target}")
                try:
                    self._run_git_action("push")
                finally:
                    hide_spinner()
            try:
                self._git.checkout_branch(source)
            except GitError as e:
                show_toast(
                    f"Checkout back failed: {e}", duration=3.0, kind=FeedbackKind.ERROR
                )
                return
            self._merge_state = None
            self._header_state.merge_target = ""
            self._clear_merge_state()
            self._tab_view.route_to("branch")
            self._branch_panel.refresh()
            show_toast(f"Merged into {target}", duration=2.0, kind=FeedbackKind.SUCCESS)

        self._alert_dialog.alert(f"Push {target} to remote?", on_push_confirmed)

    def _continue_merge(self) -> None:
        """Resume a pending merge after conflicts have been resolved."""
        state = self._merge_state
        if not state:
            show_toast("No pending merge", duration=2.0, kind=FeedbackKind.WARNING)
            return

        target = state["target"]
        source = state["source"]

        if self._git.is_merge_in_progress():
            try:
                self._git.commit_no_edit()
            except GitError as e:
                err = str(e).lower()
                if "conflict" in err or "unmerged" in err:
                    show_toast(
                        "Unresolved conflicts remain. Fix in Status, then retry.",
                        duration=3.0,
                        kind=FeedbackKind.WARNING,
                    )
                else:
                    show_toast(
                        f"Merge commit failed: {e}",
                        duration=3.0,
                        kind=FeedbackKind.ERROR,
                    )
                return

        self._confirm_push_and_finish(target, source)

    def run(self):
        if not self._repo_path:
            Console().echo(
                "@bold(@red(fatal:)) not a git repository"
                " (or any of the parent directories): .git\n"
                "\n"
                "Pigit needs a git repository to start.\n"
                "@dim(Use @green(cd) to enter one,"
                " or @green(pigit --help) to see available commands.)"
            )
            return
        try:
            self._run_body()
        except ExitEventLoop as e:
            if e.exit_code != 0:
                print(f"\n{e}\n")
