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
    AlertDialog,
    Application,
    Component,
    ComponentRoot,
    dismiss_sheet,
    exec_external,
    ExitEventLoop,
    HelpPanel,
    hide_spinner,
    keys,
    Popup,
    request_render,
    show_badge,
    show_sheet,
    show_spinner,
    show_toast,
    ToastPosition,
)
from pigit.termui._component import resolve_presented
from pigit.termui._runtime_context import get_renderer
from pigit.termui.containers import Column, Row, TabView
from pigit.termui.tty_io import terminal_size
from pigit.termui.widgets import Header
from pigit.termui.reactive import Signal
from .app_header_state import HeaderState
from .git.local_git import GitError
from .app_branch import BranchPanel
from .app_chrome import AppFooter
from .app_commit import CommitPanel
from .app_diff import DiffViewer
from .app_inspector import InspectorPanel
from .app_command_palette import CommandPalette
from .app_preview import PreviewPanel
from .app_stash import StashPanel
from .app_status import StatusPanel
from .app_theme import THEME
from .git.local_git import LocalGit
from .git.managed_repos import ManagedRepos
from .viewmodels.status import StatusViewModel
from .viewmodels.branch import BranchViewModel
from .viewmodels.commit import CommitViewModel
from .session_history import SessionHistory
from .config_data import TuiConfig

# Static help groups for HelpPanel (all operations, grouped by panel).
# Footer uses panel-specific get_help_entries() dynamically (trimmed to top-4).
_HELP_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Global",
        [
            ("1 2 3", "Switch to Status / Branch / Commit tab"),
            ("Q", "Quit Pigit"),
            ("?", "Toggle this help panel"),
            (";", "Open command palette"),
            ("I", "Toggle file inspector"),
            ("u", "Reverse last action"),
            ("U", "Open recent actions sheet"),
        ],
    ),
    (
        "Status",
        [
            ("jk/↑↓", "Navigate file list"),
            ("Enter", "Open diff for selected file"),
            ("/", "Filter files by name"),
            ("a", "Stage current file or selection"),
            ("d", "Discard changes (confirm if modified)"),
            ("i", "Add file to .gitignore"),
            ("c", "Open inline commit editor"),
            ("C", "Open external $EDITOR for commit"),
            ("v", "Toggle visual multi-select mode"),
            ("Y", "Copy file path"),
            ("E", "Open file in external $EDITOR"),
            ("o", "Checkout ours (conflict)"),
            ("t", "Checkout theirs (conflict)"),
        ],
    ),
    (
        "Stash",
        [
            ("jk/↑↓", "Navigate stash list"),
            ("Enter", "View diff for selected stash"),
            ("p", "Pop selected stash onto working tree"),
            ("d", "Drop selected stash permanently"),
        ],
    ),
    (
        "Branch",
        [
            ("jk/↑↓", "Navigate branch list"),
            ("c", "Checkout selected branch"),
            ("n", "Create new branch from current HEAD"),
            ("r", "Rename selected branch"),
            ("d", "Delete selected branch"),
            ("R", "Scope to repository subdir"),
            ("m", "Merge selected branch into current"),
        ],
    ),
    (
        "Commit",
        [
            ("jk/↑↓", "Navigate commit list"),
            ("Enter", "View commit diff"),
            ("/", "Search commits by message or author"),
            ("g", "Toggle graph / flat view"),
            ("z", "Toggle expanded commit details"),
            ("Y", "Copy commit SHA to clipboard"),
        ],
    ),
    (
        "Commit Editor",
        [
            ("Tab", "Focus body field"),
            ("Shift+Tab", "Focus subject field"),
            ("Ctrl+Enter", "Submit commit message"),
            ("Esc", "Cancel and close editor"),
        ],
    ),
    (
        "Diff",
        [
            ("jk", "Navigate diff lines"),
            ("JK", "Page up / down diff"),
            ("] [", "Jump to next / previous hunk"),
            ("H", "Toggle hunk staging mode"),
            ("v", "View file at commit"),
            ("esc", "Close diff and return to status"),
        ],
    ),
    (
        "Session History",
        [
            ("jk/↑↓", "Navigate history list"),
            ("Enter", "Reverse to selected action"),
            ("Esc", "Close panel"),
        ],
    ),
]


class TabPanel(Column):
    """Column with tab metadata for TabView routing."""

    def __init__(
        self,
        *,
        tab_name: str,
        tab_key: str,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.tab_name = tab_name
        self.tab_key = tab_key


class PigitApplication(Application):
    """Pigit TUI application entry."""

    BINDINGS = [
        ("Q", "quit"),
        ("?", "toggle_help"),
        (";", "toggle_palette"),
        ("I", "toggle_inspector"),
        ("1", "goto_status"),
        ("2", "goto_branch"),
        ("3", "goto_commit"),
        ("u", "reverse_last_action"),
        ("U", "open_recent_actions"),
    ]

    def __init__(
        self,
        *,
        local_git: LocalGit | None = None,
        managed_repos: ManagedRepos | None = None,
        config: TuiConfig,
    ) -> None:
        super().__init__(input_takeover=True)
        self._local_git = local_git or LocalGit()
        self._managed_repos = managed_repos
        self._repo_path, self._repo_conf = self._local_git.confirm_repo()
        self._git = self._local_git.bind_path(self._repo_path)
        self._inspector_visible = False
        # Header state
        self._repo_name: str = ""
        self._header_state = HeaderState(THEME)
        self._branch_signal: Signal[str] = self._header_state.branch_signal
        self._header_unsub = self._header_state.bind_to_bus(
            self._event_bus, self._TAB_CONFIG
        )
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
        # ViewModels (stored for preview updates)
        self._status_vm: StatusViewModel | None = None
        self._commit_vm: CommitViewModel | None = None
        self._branch_vm: BranchViewModel | None = None
        # Adaptive split state
        self._preview_panel: PreviewPanel | None = None
        self._is_large_screen = False
        self._preview_unsub: Callable[[], None] | None = None
        # Typed accessors for key body components (assigned in build_root)
        self._tab_view: TabView
        self._body_row: Row
        self._inspector: InspectorPanel
        self._palette: CommandPalette
        self._status_stack: Column
        self._branch_panel: BranchPanel

    LARGE_SCREEN_COLS = 120

    _TAB_CONFIG: dict[type, tuple[str, str]] = {
        StatusPanel: ("Status", "1"),
        StashPanel: ("Stash", "1"),
        BranchPanel: ("Branch", "2"),
        CommitPanel: ("Commit", "3"),
        DiffViewer: ("Display", ""),
    }

    def build_root(self) -> Component:
        footer = AppFooter(theme=THEME, id="footer")
        footer.set_global_help([("I", "Inspector"), (";", "Palette"), ("Q", "Quit")])

        self._inspector = InspectorPanel(id="inspector")

        self._status_vm = StatusViewModel(self._git, history=self._session_history)
        self._branch_vm = BranchViewModel(self._git, history=self._session_history)
        self._commit_vm = CommitViewModel(self._git)

        # Preview is created at app level but only inserted into layout when
        # Status tab is active on large screens.
        self._preview_panel = PreviewPanel(
            id="preview",
            status_vm=self._status_vm,
        )

        status_panel = StatusPanel(vm=self._status_vm, id="status_panel")
        stash_panel = StashPanel(vm=self._status_vm, id="stash")
        self._status_stack = TabPanel(
            children=[status_panel, stash_panel],
            heights=["flex", 4],
            focus_index=0,
            id="status",
            tab_name="Status",
            tab_key="1",
        )

        self._branch_panel = BranchPanel(
            vm=self._branch_vm,
            branch_signal=self._branch_signal,
            id="branch",
        )

        self._tab_view = TabView(
            children=[
                self._status_stack,
                self._branch_panel,
                CommitPanel(vm=self._commit_vm, id="commit"),
                DiffViewer(id="diff", word_diff=self._config.word_diff),
            ],
            start="status",
            on_switch=self._on_tab_switch,
            id="tab_view",
        )

        cols, _ = terminal_size()
        self._is_large_screen = cols >= self.LARGE_SCREEN_COLS

        self._body_row = Row(
            children=[
                self._tab_view,
                self._inspector,
            ],
            widths=["flex", 0],
            id="body_row",
        )

        self._palette = CommandPalette(
            on_execute=self._on_palette_execute,
            on_dismiss=self._dismiss_palette,
            id="palette",
        )

        return Column(
            children=[
                Header(
                    left=self._header_state.left,
                    center=self._header_state.center,
                    right=self._header_state.right,
                    separator=True,
                    sep_fg=THEME.fg_dim,
                    id="header",
                ),
                self._body_row,
                footer,
            ],
            heights=[2, "flex", 2],
        )

    def _on_tab_switch(self, panel: Component) -> None:
        """React to TabView switching to a new panel.

        Adjusts the adaptive layout on large screens and emits
        ``selection_changed`` so bus subscribers (footer, inspector, header,
        preview) can update themselves.
        """
        if self._is_large_screen:
            cols, _ = terminal_size()
            self._apply_body_widths(cols)
        panel.emit(EVT_SELECTION_CHANGED)

    def setup_root(self, root: ComponentRoot) -> None:
        self._help_panel = HelpPanel(
            key_fg=THEME.fg_info,
        )
        self._help_panel.set_grouped_entries(_HELP_GROUPS)
        self._help_popup = Popup(
            self._help_panel,
            exit_key=keys.KEY_ESC,
        )

    def after_start(self):
        cols, rows = terminal_size()
        if cols < 65 or rows < 10:
            assert self._loop is not None
            self._loop.quit(
                f"Terminal too small ({cols}x{rows}, need at least 65x10).",
                exit_code=1,
            )

        # Initialize layout for large screen (inserts preview only if Status is active)
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
            )

        show_toast(
            "Welcome to Pigit! Press ? for help.",
            duration=3.0,
            position=ToastPosition.BOTTOM_LEFT,
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
        # the event and update header/footer/inspector/preview.
        if self._tab_view.active is not None:
            self._on_tab_switch(self._tab_view.active)

    def _apply_body_widths(self, cols: int) -> None:
        """Recompute body_row widths based on screen size, active tab, and inspector state.

        PreviewPanel is only inserted into the layout when Status is active on
        large screens; otherwise it is removed so it does not appear global.
        """
        body_row = self._body_row
        tab_view = self._tab_view
        inspector = self._inspector
        active_presented = resolve_presented(tab_view.active)
        on_status = isinstance(active_presented, (StatusPanel, StashPanel))

        if self._is_large_screen and on_status:
            tab_w = max(50, int(cols * 0.35))
            preview_w = max(1, cols - tab_w)
            inspector_w = self._inspector_width(cols)
            desired_children = [tab_view, inspector, self._preview_panel]
            if self._inspector_visible:
                desired_widths = [tab_w, inspector_w, max(1, preview_w - inspector_w)]
            else:
                desired_widths = [tab_w, 0, preview_w]
        else:
            desired_children = [tab_view, inspector]
            if self._inspector_visible:
                desired_widths = ["flex", self._inspector_width(cols)]
            else:
                desired_widths = ["flex", 0]

        # Sync children list: preview is only present when Status is active.
        if list(body_row.children) != desired_children:
            # Detach preview if being removed
            for child in list(body_row.children):
                if child is self._preview_panel and child not in desired_children:
                    child.deactivate()
                    body_row.children.remove(child)
                    if child.parent is body_row:
                        child.parent = None
            # Attach preview if being added
            preview = self._preview_panel
            if (
                preview is not None
                and preview in desired_children
                and preview not in body_row.children
            ):
                body_row.children.append(preview)
                preview.parent = body_row
                preview.activate()
        body_row.set_widths(desired_widths)

    def toggle_help(self):
        """Toggle help popup visibility. Entries are refreshed automatically
        via HelpPanel.on_before_show before opening."""
        self._help_popup.toggle()

    def toggle_palette(self):
        """Toggle command palette visibility."""
        if self._root is None:
            return
        if self._palette.is_active:
            self._palette.close()
        else:
            self._palette.open()
            self._root.show_sheet(self._palette, height=8)

    def _dismiss_palette(self) -> None:
        """Dismiss the palette sheet from the root."""
        if self._root is not None:
            self._root.dismiss_sheet()

    def _inspector_width(self, total_width: int) -> int:
        """Compute inspector width: 30% of total, capped at 45."""
        return min(int(total_width * 0.3), 45)

    def _sync_stash_height(self, rows: int) -> None:
        """Set StashPanel height to 25% of rows, capped at 10, min 3."""
        self._status_stack.set_heights(["flex", min(max(3, int(rows * 0.25)), 10)])

    def toggle_inspector(self):
        """Toggle inspector panel visibility."""
        was_visible = self._inspector_visible
        self._inspector_visible = not self._inspector_visible
        cols, _ = terminal_size()
        self._apply_body_widths(cols)
        if self._inspector_visible:
            active = resolve_presented(self._tab_view.active)
            if not was_visible and hasattr(self._inspector, "_last_key"):
                delattr(self._inspector, "_last_key")
            self._inspector.update_from(active or self._tab_view.active)
        # Layout change invalidates the incremental-render cache so the
        # old inspector columns are fully repainted instead of visually
        # persisting as residue over the widened diff/status area.
        renderer = get_renderer()
        if renderer is not None:
            renderer.clear_cache()
        request_render()

    def resize(self, size: tuple[int, int]) -> None:
        """Recompute layout widths and stash height on terminal resize.

        Note: super().resize() is NOT called here because
        _ApplicationEventLoop.resize() already propagates resize to the
        component tree after this method returns.
        """
        cols, rows = size
        was_large = self._is_large_screen
        self._is_large_screen = cols >= self.LARGE_SCREEN_COLS
        self._sync_stash_height(rows)
        self._apply_body_widths(cols)
        if was_large and not self._is_large_screen and self._preview_panel is not None:
            self._preview_panel.clear()
        if not was_large and self._is_large_screen:
            if self._tab_view.active is not None:
                self._tab_view.active.emit(EVT_SELECTION_CHANGED)

    def goto_status(self):
        self._tab_view.route_to("status")

    def goto_branch(self):
        self._tab_view.route_to("branch")

    def goto_commit(self):
        self._tab_view.route_to("commit")

    def _refresh_active_panel(self) -> None:
        """Auto-refresh callback: refresh the currently active panel's VM.

        Skips when an overlay is open (user is in modal/sheet).
        Does NOT call request_render(); vm.refresh() uses AsyncTask,
        and Signal subscribers trigger rendering when data arrives.
        """
        active = resolve_presented(self._tab_view.active)
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

    def reverse_last_action(self) -> None:
        """Reverse the most recent session action."""
        result = self._session_history.reverse(self._git)
        if result.success:
            show_badge(result.message, duration=1.5)
            self._refresh_active_panel()
        else:
            show_toast(result.message, duration=2.0)

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

    def on_event(self, action: EventType, **data) -> bool:
        """Bridge bubbled events to the framework bus; enrich cross-cutting events.

        Application-level handlers (e.g. merge workflow) run after enrichment.
        Header, footer, inspector, and preview updates are handled by their own
        bus subscribers.
        """
        if action in (EventType("mode_changed"), EVT_SELECTION_CHANGED):
            data.setdefault("active", self._resolve_active_panel())
        if action is EventType("action_requested") and data.get("cmd") == "merge":
            self._on_merge_request(data["source"], data["target"])
            return True
        return self._event_bus.publish(action, **data)

    def _resolve_active_panel(self) -> Component | None:
        """Return the currently presented active panel, or None."""
        if self._root is None:
            return None
        return resolve_presented(self._tab_view.active)

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

    def _run_git_action(self, action: str) -> None:
        """Run a git action via exec_external and show result toast."""
        try:
            result = exec_external(["git", action], cwd=self._repo_path)
            if result.returncode == 0:
                show_toast(f"Git {action} completed", duration=1.5)
            else:
                stderr = result.stderr.strip() if result.stderr else "Unknown error"
                show_toast(f"Git {action} failed: {stderr}", duration=3.0)
        except Exception as e:
            show_toast(f"Git {action} error: {e}", duration=3.0)

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
        """On startup: recover pending merge state if merge is still in progress."""
        state = self._load_merge_state()
        if state is None:
            return
        if self._git.is_merge_in_progress():
            self._merge_state = state
            self._header_state.merge_target = state.get("target", "")
            show_toast(
                f"Resume merge: {state['source']} \u2192 {state['target']} (continue-merge)",
                duration=3.0,
            )
        else:
            self._clear_merge_state()
            self._header_state.merge_target = ""

    def _on_merge_request(self, source: str, target: str) -> None:
        """Callback from BranchPanel: confirm then execute merge workflow."""

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
                    )
                    self._tab_view.route_to("status")
                    return
                show_toast(f"Merge failed: {e}", duration=3.0)
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
                show_toast(f"Checkout back failed: {e}", duration=3.0)
                return
            self._merge_state = None
            self._header_state.merge_target = ""
            self._clear_merge_state()
            self._tab_view.route_to("branch")
            self._branch_panel.refresh()
            show_toast(f"Merged into {target}", duration=2.0)

        self._alert_dialog.alert(f"Push {target} to remote?", on_push_confirmed)

    def _continue_merge(self) -> None:
        """Resume a pending merge after conflicts have been resolved."""
        state = self._merge_state
        if not state:
            show_toast("No pending merge", duration=2.0)
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
                    )
                else:
                    show_toast(f"Merge commit failed: {e}", duration=3.0)
                return

        self._confirm_push_and_finish(target, source)

    def quit(self, *, exit_code: int = 0, result_message: str | None = None):
        raise ExitEventLoop("Quit", exit_code=exit_code, result_message=result_message)

    def run(self):
        try:
            self._run_body()
        except ExitEventLoop as e:
            if e.exit_code != 0:
                print(f"\n{e}\n")
