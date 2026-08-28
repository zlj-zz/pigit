"""
Module: pigit/app.py
Description: Git TUI panels and application entry.
Author: Zev
Date: 2026-04-17
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pigit.termui import (
    EventType,
    EVT_GOTO,
    EVT_SELECTION_CHANGED,
    FeedbackKind,
    bind_action,
    Application,
    Component,
    ComponentRoot,
    dismiss_sheet,
    ExitEventLoop,
    get_renderer,
    keys,
    AsyncTask,
    request_render,
    resolve_presentation_leaf,
    run_async,
    Segment,
    show_badge,
    show_sheet,
    show_toast,
    ToastPosition,
    set_theme,
)
from pigit.termui.cli_output import Console
from pigit.termui.containers import Column, SplitPane, TabView, ExclusiveView
from pigit.termui.tty_io import terminal_size
from pigit.termui.widgets import AlertDialog, BindingBrowser, Header, Popup
from pigit.termui.bindings import ExecutableBinding
from pigit.termui.reactive import Signal
from .app_header_state import HeaderState
from .app_merge_state import MergeStateStore
from .app_observe import ObserveDeps, ObserveHost
from .app_panel_nav import PanelNavigator
from .app_network_git import NetworkGit, NetworkGitOutcome
from .app_merge_workflow import MergeWorkflow
from .app_sequencer import SequencerControl
from .git.api import GitApi
from .app_branch import BranchPanel
from .app_chrome import AppFooter
from .app_commit import CommitPanel
from .app_diff import DiffViewer
from .app_inspector import InspectorSheet
from .app_types import InspectorHost, InspectorSnapshot
from .app_command_palette import CommandPalette
from .app_preview import PreviewPanel
from .app_log_graph_preview import LogGraphPreview
from .app_stash import StashPanel
from .app_status import StatusPanel
from .app_theme import THEME
from .git.managed_repos import ManagedRepos
from .observe.overlay import should_defer_repo_refresh
from .repo_session import RepoSession
from .session_history import SessionHistory
from .config_data import AppConfig

# Footer chrome height in rows. The layout height (build_root) and the
# toast_bottom_pad (setup_root) both derive from this constant, so growing
# the footer can never silently overlap bottom-anchored toasts.
FOOTER_HEIGHT = 2


class PigitApplication(Application):
    """Pigit TUI application entry."""

    keymap_namespace = "universal"
    min_terminal_size = (65, 10)
    LARGE_SCREEN_COLS = 120

    # Body tree — assigned in build_root; required for a live TUI session.
    _tab_view: TabView
    _split_pane: SplitPane
    _body_view: ExclusiveView
    _palette: CommandPalette
    _status_stack: Column
    _status_panel: StatusPanel
    _stash_panel: StashPanel
    _branch_panel: BranchPanel
    _commit_panel: CommitPanel
    _diff_panel: DiffViewer
    _panel_nav: PanelNavigator

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
        # Undo stack must exist before RepoSession.build (Status/Branch VMs).
        self._session_history = SessionHistory(max_items=100, max_memory_mb=50)
        self._session = RepoSession.build(
            self._git_api, None, self._session_history
        )
        # Aliases keep existing lambdas (get_git=lambda: self._git, …) working.
        self._git = self._session.git
        self._repo_path = self._session.repo_path
        self._repo_name = self._session.repo_name
        self._status_vm = self._session.status_vm
        self._commit_vm = self._session.commit_vm
        self._branch_vm = self._session.branch_vm
        # Header state
        self._header_state = HeaderState(THEME)
        self._branch_signal: Signal[str] = self._header_state.branch_signal
        self._header_unsub = self._header_state.bind_to_bus(self._event_bus)
        self._merge_state_store = MergeStateStore(
            self._header_state,
            get_git_dir=self._git.get_git_dir,
        )
        self._alert_dialog = AlertDialog(
            inner_width=50,
            on_result=lambda _: None,
        )
        self._config = config
        self._observe_host: ObserveHost | None = None
        self._header_reload_token: object | None = None
        # Inspector async-load state
        self._inspector_task: AsyncTask | None = None
        self._inspector_token: object = None
        # Background push/pull (must not use exec_external on the worker)
        self._network_sync_task: AsyncTask[NetworkGitOutcome] = AsyncTask()
        self._network_git = NetworkGit(
            store=self._merge_state_store,
            get_git=lambda: self._git,
            navigate_product=self.navigate_product,
            get_sync_task=lambda: self._network_sync_task,
            get_refresh_git_vms=lambda: self._refresh_git_vms(),
            get_schedule_reload_header=lambda: self._schedule_reload_header(),
            get_alert_dialog=lambda: self._alert_dialog,
        )
        self._merge_workflow = MergeWorkflow(
            store=self._merge_state_store,
            network=self._network_git,
            get_git=lambda: self._git,
            navigate_product=self.navigate_product,
            get_branch_panel=lambda: self._branch_panel,
            get_alert_dialog=lambda: self._alert_dialog,
            get_refresh_git_vms=lambda: self._refresh_git_vms(),
            get_schedule_reload_header=lambda: self._schedule_reload_header(),
        )
        self._sequencer = SequencerControl(
            get_git=lambda: self._git,
            get_repo_path=lambda: self._repo_path,
            navigate_product=self.navigate_product,
            get_alert_dialog=lambda: self._alert_dialog,
            get_refresh_git_vms=lambda: self._refresh_git_vms(),
            get_refresh_active_panel=lambda: self._refresh_active_panel(),
        )
        # Adaptive split state
        self._preview_panel: PreviewPanel | None = None
        self._log_graph_preview: LogGraphPreview | None = None
        self._is_large_screen = False
        self._diff_preview_wanted = config.diff_preview_default
        self._log_graph_wanted = config.log_graph_default
        self._preview_unsub: Callable[[], None] | None = None

    def build_root(self) -> Component:
        footer = AppFooter(theme=THEME, id="footer")
        footer.set_global_help([(";", "Palette"), ("I", "Inspector"), ("Q", "Quit")])

        # Side previews are created at app level but only inserted into the
        # layout on large screens: Status/Stash use diff preview, Branch uses
        # the log-graph preview. At most one is in the split pane at a time.
        # VMs come from self._session (aliases set in __init__).
        self._preview_panel = PreviewPanel(
            id="preview",
            status_vm=self._status_vm,
            on_preview_target=lambda rel: (
                self._observe_host.set_preview_target(rel)
                if self._observe_host
                else None
            ),
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
            file_icons=self._config.file_icons,
        )
        self._stash_panel = StashPanel(
            vm=self._status_vm,
            id="stash",
            on_toggle_preview=self.toggle_side_preview,
        )
        status_panel = self._status_panel
        stash_panel = self._stash_panel
        self._status_stack = Column(
            children=[status_panel, stash_panel],
            heights=["flex", 4],
            focus_index=0,
            id="status",
        )
        status_stack = self._status_stack

        self._branch_panel = BranchPanel(
            vm=self._branch_vm,
            branch_signal=self._branch_signal,
            id="branch",
            on_toggle_preview=self.toggle_side_preview,
        )
        branch_panel = self._branch_panel

        self._commit_panel = CommitPanel(
            vm=self._commit_vm,
            id="commit",
            report_default=self._config.commit_report_default,
        )
        commit_panel = self._commit_panel
        self._diff_panel = DiffViewer(id="diff", word_diff=self._config.word_diff)
        self._tab_view = TabView(
            children=[
                status_stack,
                branch_panel,
                commit_panel,
            ],
            start="status",
            on_switch=self._on_tab_switch,
            id="tab_view",
        )
        tab_view = self._tab_view

        cols, _ = terminal_size()
        self._is_large_screen = cols >= self.LARGE_SCREEN_COLS

        self._split_pane = SplitPane(
            master=tab_view,
            breakpoint_cols=self.LARGE_SCREEN_COLS,
            id="split_pane",
        )
        self._body_view = ExclusiveView(
            [self._split_pane, self._diff_panel],
            visible=self._split_pane,
            id="body",
        )

        self._palette = CommandPalette(
            on_execute=self._on_palette_execute,
            on_dismiss=self._dismiss_palette,
            id="palette",
        )

        children = [
            Header(
                left=self._header_state.left,
                right=self._header_state.right,
                separator=True,
                sep_fg=THEME.fg_dim,
                id="header",
            ),
            self._body_view,
        ]
        heights: list = [2, "flex"]
        if self._config.show_footer:
            children.append(footer)
            heights.append(FOOTER_HEIGHT)

        self._panel_nav = PanelNavigator(
            get_tab_view=lambda: tab_view,
            get_status_stack=lambda: status_stack,
            get_status_panel=lambda: status_panel,
            get_stash_panel=lambda: stash_panel,
            get_branch_panel=lambda: branch_panel,
            get_commit_panel=lambda: commit_panel,
        )
        self._observe_host = ObserveHost(
            ObserveDeps(
                get_git=lambda: self._git,
                get_repo_path=lambda: self._repo_path,
                get_config=lambda: self._config,
                get_status_vm=lambda: self._status_vm,
                get_tab_view=lambda: tab_view,
                get_preview_panel=lambda: self._preview_panel,
                get_log_graph_preview=lambda: self._log_graph_preview,
                get_diff_preview_wanted=lambda: self._diff_preview_wanted,
                get_log_graph_wanted=lambda: self._log_graph_wanted,
                get_is_large_screen=lambda: self._is_large_screen,
                get_root=lambda: self._root,
                get_loop=lambda: self._loop,
                schedule_reload_header=self._schedule_reload_header,
                refresh_header_dirty=self._refresh_header_dirty,
                refresh_list_panel=self._refresh_list_panel,
            )
        )
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
        if self._observe_host is not None:
            self._observe_host.on_tab_switch()

    def setup_root(self, root: ComponentRoot) -> None:
        # Footer occupies FOOTER_HEIGHT rows when shown; keep toasts above it.
        root.toast_bottom_pad = FOOTER_HEIGHT if self._config.show_footer else 0
        self._help_browser = BindingBrowser(
            key_fg=THEME.fg_info,
            on_invoke_error=self._on_help_invoke_error,
        )
        self._help_browser.set_groups(self.get_help_groups())
        self._help_popup = Popup(
            self._help_browser,
            exit_key=keys.KEY_ESC,
        )

    def _on_help_invoke_error(self, exc: BaseException) -> None:
        """Toast after Help dismiss when an invoked binding raises."""
        show_toast(str(exc) or "Action failed", duration=2.5, kind=FeedbackKind.ERROR)

    def get_help_groups(self) -> list[tuple[str, list[ExecutableBinding]]]:
        """Help for the active presentation panel, then Global app bindings."""
        groups: list[tuple[str, list[ExecutableBinding]]] = []
        active = self._resolve_active_panel()
        if active is not None:
            entries = active.get_executable_bindings()
            if entries:
                title_fn = getattr(active, "get_help_title", None)
                title = str(title_fn()) if callable(title_fn) else type(active).__name__
                groups.append((title, entries))
        universal = self.get_executable_bindings()
        if universal:
            groups.append(("Global", universal))
        return groups

    def _open_help_browser(self) -> None:
        """Rebuild groups and show Help when the popup is closed."""
        popup = self._help_popup
        browser = self._help_browser
        if popup is None or browser is None:
            return
        browser.set_groups(self.get_help_groups())
        if not popup.open:
            popup.toggle()

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
            self._schedule_reload_header()
        except Exception:
            logging.warning("Failed to initialize repo info", exc_info=True)
            show_toast(
                "Failed to load repo info. Check git configuration.",
                duration=3.0,
                position=ToastPosition.BOTTOM_LEFT,
                kind=FeedbackKind.ERROR,
            )

        self._merge_state_store.try_restore(self._git.is_merge_in_progress)
        self._maybe_show_welcome_on_first_run()

        if self._config.repo_observe and self._observe_host is not None:
            self._observe_host.start()

        # Initial sync: all components are mounted now, so subscribers receive
        # the event and update header/footer/preview.
        if self._tab_view.visible is not None:
            self._on_tab_switch(self._tab_view.visible)

    def _maybe_show_welcome_on_first_run(self) -> None:
        """Open Welcome Sheet once when :func:`should_auto_show_welcome` allows."""
        from .app_welcome import build_welcome_content, should_auto_show_welcome
        from .welcome_state import save_welcome_seen

        if self._root is None:
            return
        rows = build_welcome_content(self)
        if not should_auto_show_welcome(
            self._config,
            self._root,
            min_terminal_rows=self.min_terminal_size[1],
            content_rows=len(rows),
        ):
            return
        self._show_welcome(on_dismiss=save_welcome_seen, rows=rows)

    def _show_welcome(
        self,
        *,
        on_dismiss: Callable[[], None],
        rows: list | None = None,
    ) -> None:
        """Open Welcome Sheet with the given dismiss callback."""
        from .app_welcome import (
            WELCOME_SHEET_MAX_FRACTION,
            WelcomeSheet,
            build_welcome_content,
        )

        content = rows if rows is not None else build_welcome_content(self)
        sheet = WelcomeSheet(on_dismiss=on_dismiss, rows=content)
        show_sheet(
            sheet,
            edge="top",
            title="Welcome to Pigit",
            max_fraction=WELCOME_SHEET_MAX_FRACTION,
        )
        sheet.mount()

    @bind_action("show_welcome", desc="Show welcome guide", tip="Welcome")
    def show_welcome(self) -> None:
        """Open the onboarding Welcome sheet (no-op when another overlay is open)."""
        if self._root is None or self._root.has_overlay_open():
            return
        self._show_welcome(on_dismiss=lambda: None)

    def on_exit(self) -> None:
        """Stop repo observation and dispose the current repo session.

        ``observe.stop`` is best-effort cleanup; the session must always be
        disposed (ObserveHost holds a status_vm items subscription).
        """
        try:
            if self._observe_host is not None:
                self._observe_host.stop()
        finally:
            self._session.dispose()

    def _start_repo_observe(self) -> None:
        """Delegate to ObserveHost.start()."""
        if self._observe_host is not None:
            self._observe_host.start()

    def _build_observe_roots(self):
        """Delegate to ObserveHost.build_roots()."""
        if self._observe_host is None:
            return []
        return self._observe_host.build_roots()

    def _resync_observe_roots(self, *, reset: bool = False) -> None:
        """Delegate to ObserveHost.resync_roots()."""
        if self._observe_host is not None:
            self._observe_host.resync_roots(reset=reset)

    def _stop_repo_observe(self) -> None:
        """Delegate to ObserveHost.stop()."""
        if self._observe_host is not None:
            self._observe_host.stop()

    def _on_observe_batch(self, batch) -> None:
        """Delegate to ObserveHost.on_batch()."""
        if self._observe_host is not None:
            self._observe_host.on_batch(batch)

    def _refresh_header_dirty(self) -> None:
        """Update just the worktree dirty dot from the observe digest.

        Worktree edits cannot change branch tracking, so skip the full header
        reload (two git subprocesses per batch) and reuse the digest the
        observe poll already computed. Called from on_batch for
        WORKTREE_META/INDEX/STASH kinds.
        """
        if self._observe_host is None:
            return
        observed = self._observe_host.worktree_dirty
        if observed is None:
            # Worktree observe not active on this tab; nothing fresh to read.
            return
        self._header_state.dirty = observed

    def _header_dirty_probe(self) -> bool:
        """Dirty flag from observe digest when active, else a direct probe.

        The observe host already runs ``git status --porcelain`` on every poll;
        reusing its last digest avoids a second git call per header refresh.
        """
        if self._observe_host is not None:
            observed = self._observe_host.worktree_dirty
            if observed is not None:
                return observed
        return self._git.is_worktree_dirty()

    def _schedule_reload_header(self) -> None:
        """Async-load branch/ahead/behind + dirty into HeaderState.

        The git probes run in the worker thread; ``apply`` only writes Signal
        state on the UI thread (never runs git).
        """
        token = object()
        self._header_reload_token = token

        def worker() -> tuple[str, int, int, bool]:
            head, ahead, behind = self._git.get_head_tracking()
            return head, ahead, behind, self._header_dirty_probe()

        def apply(result: tuple[str, int, int, bool]) -> None:
            if token is not self._header_reload_token:
                return
            branch, ahead, behind, dirty = result
            self._header_state.branch = branch
            self._header_state.ahead = ahead
            self._header_state.behind = behind
            self._header_state.dirty = dirty

        run_async(worker, apply)

    def _side_preview_for_active(self) -> Component | None:
        """Return the one large-screen side panel for the current tab, or None."""
        if self._is_detail_open() or not self._is_large_screen:
            return None
        active = resolve_presentation_leaf(self._tab_view.visible)
        if isinstance(active, (StatusPanel, StashPanel)):
            return self._preview_panel if self._diff_preview_wanted else None
        if isinstance(active, BranchPanel):
            return self._log_graph_preview if self._log_graph_wanted else None
        return None

    def _apply_body_widths(self, cols: int) -> None:
        """Update SplitPane detail and widths for the active tab."""
        if self._is_detail_open():
            return
        active = resolve_presentation_leaf(self._tab_view.visible)
        if isinstance(active, (StatusPanel, StashPanel)):
            self._split_pane.set_detail(self._preview_panel)
            self._split_pane.set_detail_wanted(
                self._is_large_screen and self._diff_preview_wanted
            )
        elif isinstance(active, BranchPanel):
            self._split_pane.set_detail(self._log_graph_preview)
            self._split_pane.set_detail_wanted(
                self._is_large_screen and self._log_graph_wanted
            )
        else:
            self._split_pane.set_detail(None)
            self._split_pane.set_detail_wanted(False)
        self._split_pane.apply_terminal_width(cols)

    @bind_action("help", "?", desc="Toggle this help panel", tip="Help")
    def toggle_help(self):
        """Toggle help popup visibility. Rebuild groups so Commit's title tracks log_ref."""
        popup = self._help_popup
        if popup is None:
            return
        if popup.open:
            popup.toggle()
            return
        self._open_help_browser()

    @bind_action("palette", ";", desc="Open command palette", tip="Palette")
    def toggle_palette(self):
        """Toggle command palette visibility."""
        if self._root is None:
            return
        if self._palette.is_active:
            self._palette.close()
        else:
            from pigit.app_command_palette import catalog_for_context
            from pigit.termui.widgets import list_slots_for_term

            # Same height source as Sheet.resolve_height (root size, not a
            # second terminal_size() read that can disagree after resize).
            term_h = self._root._size[1]
            if term_h <= 0:
                term_h = terminal_size()[1]
            slots = list_slots_for_term(term_h)
            try:
                sequencer = self._git.sequencer_in_progress()
            except Exception:
                sequencer = None
            self._palette.open(
                items=catalog_for_context(sequencer),
                list_slots=slots,
            )
            self._root.show_sheet(self._palette, title="Commands")

    @bind_action("goto_status", "1", desc="Switch to Status panel", tip="Status")
    def goto_status(self):
        """Switch focus to the Status panel."""
        self._close_detail_if_open()
        self._focus_destination(self._status_panel)

    @bind_action("goto_stash", "2", desc="Switch to Stash panel", tip="Stash")
    def goto_stash(self):
        """Switch focus to the Stash panel."""
        self._close_detail_if_open()
        self._focus_destination(self._stash_panel)

    @bind_action("goto_branch", "3", desc="Switch to Branch tab", tip="Branch")
    def goto_branch(self):
        """Switch focus to the Branch panel."""
        self._close_detail_if_open()
        self._focus_destination(self._branch_panel)

    @bind_action("goto_commit", "4", desc="Switch to Commit tab", tip="Commit")
    def goto_commit(self):
        """Switch focus to the Commit panel."""
        self._close_detail_if_open()
        self._focus_destination(self._commit_panel)

    @bind_action(
        "next_panel",
        "tab",
        desc="Cycle to next panel (Status, Stash, Branch, Commit)",
    )
    def next_panel(self) -> None:
        """Cycle focus to the next panel in the Status → Stash → Branch → Commit ring."""
        self._close_detail_if_open()
        self._cycle_panel(1)

    @bind_action(
        "prev_panel",
        "shift tab",
        desc="Cycle to previous panel (Status, Stash, Branch, Commit)",
    )
    def prev_panel(self) -> None:
        """Cycle focus to the previous panel in the Status → Stash → Branch → Commit ring."""
        self._close_detail_if_open()
        self._cycle_panel(-1)

    def _panel_ring(self) -> tuple[Component, ...]:
        """Return the four panels that Tab/Shift+Tab cycle through, in order."""
        return self._panel_nav.panel_ring()

    def _ring_index(self) -> int | None:
        """Index in the panel ring from the product TabView."""
        return self._panel_nav.ring_index()

    def _focus_destination(self, panel: Component) -> None:
        """Move TabView + Status/Stash column focus to *panel*."""
        self._panel_nav.focus_destination(panel)

    def _cycle_panel(self, step: int) -> None:
        """Move focus ``step`` positions around the panel ring."""
        self._panel_nav.cycle_panel(step)

    def _is_detail_open(self) -> bool:
        """True when Diff occupies the body ExclusiveView slot."""
        body = getattr(self, "_body_view", None)
        return body is not None and body.visible is self._diff_panel

    def _reveal_product(self) -> None:
        """Close Diff detail if open and resync SplitPane layout for the terminal."""
        if not self._is_detail_open():
            return
        self._body_view.show(self._split_pane)
        cols, _ = terminal_size()
        self._apply_body_widths(cols)

    def _close_detail_if_open(self) -> None:
        """Hide Diff detail without unmounting it; resync product layout."""
        self._reveal_product()

    def presentation_active(self) -> Component | None:
        """Presentation leaf: Diff when detail open, else product tab leaf."""
        if self._is_detail_open():
            return self._diff_panel
        tab = getattr(self, "_tab_view", None)
        if tab is None:
            return None
        return resolve_presentation_leaf(tab.visible)

    def navigate_product(self, target: str) -> None:
        """Close Diff detail if open, then route the product TabView."""
        self._reveal_product()
        tab = getattr(self, "_tab_view", None)
        if tab is not None:
            tab.route_to(target)

    def _handle_body_goto(self, **data) -> bool:
        """Own all EVT_GOTO: open Diff detail, or product panel navigation."""
        target = data.get("target")
        if target == "diff" or target is self._diff_panel:
            self._diff_panel.update(EVT_GOTO, **data)
            self._body_view.show(self._diff_panel)
            return True
        was_detail_open = self._is_detail_open()
        if was_detail_open:
            self._reveal_product()
        panel = self._panel_nav.resolve_panel(target)
        if panel is not None:
            self._panel_nav.focus_destination(panel)
            return True
        return was_detail_open

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
        show_sheet(panel, title="Recent")
        panel.mount()

    def toggle_side_preview(self) -> None:
        """Toggle the side preview that belongs to the focused panel."""
        if self._is_detail_open():
            return
        cols, _ = terminal_size()
        if cols < self.LARGE_SCREEN_COLS:
            show_toast(
                f"Need at least {self.LARGE_SCREEN_COLS} columns for preview",
                duration=2.0,
                kind=FeedbackKind.WARNING,
            )
            return
        active = resolve_presentation_leaf(self._tab_view.visible)
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
            if self._tab_view.visible is not None:
                self._tab_view.visible.emit(EVT_SELECTION_CHANGED)
        elif hidden is not None:
            hidden.clear()
        renderer = get_renderer()
        if renderer is not None:
            renderer.clear_cache()
        request_render()

    @bind_action("inspector", "I", desc="Inspect selection", tip="Inspector")
    def open_inspector(self) -> None:
        """Open a frozen top-edge snapshot of the current selection.

        The snapshot build spawns several git subprocesses, so it runs on an
        AsyncTask worker; the sheet appears immediately with a loading hint.
        """
        active = self.presentation_active()
        if not isinstance(active, InspectorHost):
            show_toast(
                "No inspector for this view",
                duration=1.5,
                kind=FeedbackKind.INFO,
            )
            return
        self._cancel_inspector_load()
        token = object()
        self._inspector_token = token
        placeholder = InspectorSheet([[Segment("Inspecting…", fg=THEME.fg_dim)]])
        placeholder_sheet = show_sheet(placeholder, height=3, edge="top")
        placeholder.mount()

        def load() -> InspectorSnapshot | None:
            return active.get_inspector_snapshot()

        def apply(snapshot: InspectorSnapshot | None) -> None:
            if token != self._inspector_token:
                return  # superseded by a newer I press
            if placeholder_sheet is None or not placeholder_sheet.open:
                return  # user closed the inspector while it was loading
            dismiss_sheet()
            if snapshot is None:
                show_toast(
                    "Nothing to inspect",
                    duration=1.5,
                    kind=FeedbackKind.INFO,
                )
                return
            lines = InspectorSheet.format(snapshot)
            sheet = InspectorSheet(lines)
            show_sheet(sheet, edge="top", max_fraction=0.5)
            sheet.mount()

        self._inspector_task = run_async(load, apply)

    def _cancel_inspector_load(self) -> None:
        """Invalidate any in-flight inspector load so its result is dropped."""
        self._inspector_token = None
        if self._inspector_task is not None:
            self._inspector_task.cancel()
            self._inspector_task = None

    @bind_action("quit", "Q", "q", desc="Quit Pigit", tip="Quit")
    def quit(self, *, exit_code: int = 0, result_message: str | None = None):
        raise ExitEventLoop("Quit", exit_code=exit_code, result_message=result_message)

    @bind_action(
        "push", "P", desc="Push current branch (set upstream if needed)", tip="Push"
    )
    def push_upstream(self) -> None:
        """Push HEAD; confirm ``git push -u`` when no upstream is configured."""
        self._run_network_git("push")

    @bind_action("pull", "F", desc="Pull current branch from upstream", tip="Pull")
    def pull_upstream(self) -> None:
        """Pull into HEAD from its configured upstream (non-interactive)."""
        self._run_network_git("pull")

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
            if self._tab_view.visible is not None:
                self._tab_view.visible.emit(EVT_SELECTION_CHANGED)

    def _refresh_list_panel(self, panel: Component) -> None:
        """Refresh a list panel via an overridden ``refresh`` or its ViewModel."""
        from pigit.termui.component import Component as ComponentBase

        if type(panel).refresh is not ComponentBase.refresh:
            panel.refresh()
            return
        vm = getattr(panel, "_vm", None)
        if vm is not None and hasattr(vm, "refresh"):
            vm.refresh()

    def _refresh_active_panel(self) -> None:
        """Imperative refresh of the currently presented product panel.

        Used after actions (rebase/merge done, etc.). Skips when a MODAL or
        SHEET is open (toasts do not block). Does not call ``request_render``;
        ViewModel refresh uses AsyncTask and Signal subscribers render.
        Skips while Diff detail is open (do not refresh a hidden list).
        """
        if self._is_detail_open():
            return
        active = resolve_presentation_leaf(self._tab_view.visible)
        if active is None:
            return
        if self._root is not None and should_defer_repo_refresh(self._root):
            return
        self._refresh_list_panel(active)

    def _on_rebase_request(self, target: str) -> None:
        """Open the interactive-rebase todo panel for ``target``."""
        self._sequencer.on_rebase_request(target)

    def on_event(self, action: EventType, **data) -> bool:
        """Bridge bubbled events to the framework bus; enrich cross-cutting events.

        Application-level handlers (e.g. merge workflow) run after enrichment.
        Header, footer, and preview updates are handled by their own
        bus subscribers.
        """
        if action is EVT_GOTO:
            return self._handle_body_goto(**data)
        if action in (EventType("mode_changed"), EVT_SELECTION_CHANGED):
            data.setdefault("active", self.presentation_active())
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
        return self.presentation_active()

    def _pin_log_ref(self, ref: str, *, announce: bool = True) -> None:
        """Pin the Commit log to ``ref``; announce unless it is the checkout."""
        self._commit_vm.set_log_ref(ref)
        if announce and not self._commit_vm.viewing_checkout_log():
            show_toast(f"Showing log: {ref}", duration=1.5, kind=FeedbackKind.INFO)

    def _on_show_log(self, ref: str) -> None:
        """Pin Commit log to ``ref`` and open the Commit tab."""
        self._pin_log_ref(ref)
        already_on_commit = self._tab_view.visible is self._commit_panel
        self.navigate_product("commit")
        if already_on_commit:
            # Already on Commit (route_to no-ops); refresh the title directly.
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
        from pigit.app_command_palette import KNOWN_COMMAND_IDS

        lower = cmd.lower().strip()
        if lower not in KNOWN_COMMAND_IDS:
            show_toast(
                f"Unknown command: {cmd}",
                duration=1.5,
                kind=FeedbackKind.WARNING,
            )
            return
        if lower == "quit":
            self.quit()
            return
        if lower == "stash":
            self.goto_stash()
            return
        if lower in ("status", "branch", "commit"):
            self.navigate_product(lower)
            return
        if lower in ("pull", "push"):
            self._run_network_git(lower)
            return
        if lower == "fetch":
            self._run_git_action("fetch")
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

    @property
    def _network_sync_busy(self) -> bool:
        """Backward-compatible busy flag for network push/pull."""
        return self._network_git.busy

    @_network_sync_busy.setter
    def _network_sync_busy(self, value: bool) -> None:
        self._network_git.busy = value

    def _run_network_git(
        self,
        action: str,
        *,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Delegate to NetworkGit.run()."""
        self._network_git.run(action, on_complete=on_complete)

    def _handle_pull_conflict(self, message: str) -> None:
        """Delegate to NetworkGit.handle_pull_conflict()."""
        self._network_git.handle_pull_conflict(message)

    def _run_git_action(self, action: str) -> None:
        """Delegate to SequencerControl.run_git_action()."""
        self._sequencer.run_git_action(action)

    def _run_rebase_control(self, action: str) -> None:
        """Delegate to SequencerControl.run_rebase_control()."""
        self._sequencer.run_rebase_control(action)

    def _refresh_git_vms(self) -> None:
        """Refresh Status, Branch, and Commit VMs (safe while a palette overlay is open)."""
        self._status_vm.refresh()
        self._branch_vm.refresh()
        self._commit_vm.refresh()

    def _do_rebase_control(self, flag: str) -> None:
        """Delegate to SequencerControl.do_rebase_control()."""
        self._sequencer.do_rebase_control(flag)

    def _run_cherry_pick_control(self, action: str) -> None:
        """Delegate to SequencerControl.run_cherry_pick_control()."""
        self._sequencer.run_cherry_pick_control(action)

    def _do_cherry_pick_control(self, flag: str) -> None:
        """Delegate to SequencerControl.do_cherry_pick_control()."""
        self._sequencer.do_cherry_pick_control(flag)

    def _on_cherry_pick(self, sha: str, is_merge: bool) -> None:
        """Delegate to SequencerControl.on_cherry_pick()."""
        self._sequencer.on_cherry_pick(sha, is_merge)

    def _exec_cherry_pick(self, sha: str) -> None:
        """Delegate to SequencerControl.exec_cherry_pick()."""
        self._sequencer.exec_cherry_pick(sha)

    def _finish_cherry_pick(self, result, sha: str) -> None:
        """Delegate to SequencerControl.finish_cherry_pick()."""
        self._sequencer.finish_cherry_pick(result, sha)

    def _on_merge_request(self, source: str, target: str) -> None:
        """Delegate to MergeWorkflow.on_merge_request()."""
        self._merge_workflow.on_merge_request(source, target)

    def _do_merge_workflow(self, source: str, target: str) -> None:
        """Delegate to MergeWorkflow.do_merge_workflow()."""
        self._merge_workflow.do_merge_workflow(source, target)

    def _confirm_push_and_finish(self, target: str, source: str) -> None:
        """Delegate to MergeWorkflow.confirm_push_and_finish()."""
        self._merge_workflow.confirm_push_and_finish(target, source)

    def _finish_merge_checkout(self, target: str, source: str) -> None:
        """Delegate to MergeWorkflow.finish_merge_checkout()."""
        self._merge_workflow.finish_merge_checkout(target, source)

    def _continue_merge(self) -> None:
        """Delegate to MergeWorkflow.continue_merge()."""
        self._merge_workflow.continue_merge()

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
