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

from pigit.termui import (
    ActionEventType,
    AlertDialog,
    Application,
    by_id,
    Column,
    Component,
    ComponentRoot,
    exec_external,
    ExitEventLoop,
    Header,
    HelpPanel,
    hide_spinner,
    keys,
    Popup,
    Row,
    show_spinner,
    show_toast,
    TabView,
    ToastPosition,
)
from pigit.termui.reactive import Signal
from .app_header_state import HeaderState
from .git.local_git import GitError
from .app_branch import BranchPanel
from .app_chrome import AppFooter
from .app_commit import CommitPanel
from .app_diff import DiffViewer
from .app_inspector import InspectorPanel
from .app_command_palette import CommandPalette
from .app_status import StatusPanel
from .app_theme import THEME
from .git.local_git import LocalGit
from .git.managed_repos import ManagedRepos


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
    ]

    def __init__(
        self,
        local_git: LocalGit | None = None,
        managed_repos: ManagedRepos | None = None,
    ) -> None:
        super().__init__(input_takeover=True)
        self._local_git = local_git or LocalGit()
        self._managed_repos = managed_repos
        self._repo_path, self._repo_conf = self._local_git.confirm_repo()
        if self._repo_path and self._managed_repos is not None:
            try:
                from .context import Context

                ctx = Context.try_current()
                if ctx is not None and ctx.config.get().repo.auto_append:
                    self._managed_repos.add_repos([self._repo_path])
            except Exception:
                logging.debug("auto_append failed", exc_info=True)
        self._git = self._local_git.bind_path(self._repo_path)
        self._inspector_visible = False
        # Header state
        self._repo_name: str = ""
        self._header_state = HeaderState(THEME)
        self._branch_signal: Signal[str] = self._header_state.branch_signal
        # Merge workflow state
        self._merge_state: dict | None = None
        self._alert_dialog = AlertDialog(
            inner_width=50,
            on_result=lambda _: None,
        )

    _TAB_CONFIG: dict[type, tuple[str, str]] = {
        StatusPanel: ("Status", "1"),
        BranchPanel: ("Branch", "2"),
        CommitPanel: ("Commit", "3"),
        DiffViewer: ("Display", ""),
    }

    def build_root(self) -> Component:
        DiffViewer(id="diff")
        StatusPanel(display=by_id("diff"), git=self._git, id="status")
        BranchPanel(
            git=self._git,
            branch_signal=self._branch_signal,
            id="branch",
        )
        CommitPanel(display=by_id("diff"), git=self._git, id="commit")

        def _on_tab_switch(panel: Component) -> None:
            footer = by_id("footer", AppFooter)
            provider = getattr(panel, "get_help_entries", None)
            footer.set_help_provider(provider)
            self._header_state.tab, self._header_state.tab_key = self._TAB_CONFIG.get(
                type(panel), ("", "")
            )
            by_id("inspector", InspectorPanel).update_from(panel)

        TabView(
            children=[by_id("status"), by_id("branch"), by_id("commit"), by_id("diff")],
            start="status",
            on_switch=_on_tab_switch,
            id="tab_view",
        )

        Header(
            left=self._header_state.left,
            center=self._header_state.center,
            right=self._header_state.right,
            separator=True,
            sep_fg=THEME.fg_dim,
            id="header",
        )
        footer = AppFooter(theme=THEME, id="footer")
        footer.set_global_help([("Q", "Quit"), ("I", "Inspector"), (";", "Palette")])
        provider = getattr(by_id("tab_view", TabView).active, "get_help_entries", None)
        footer.set_help_provider(provider)

        InspectorPanel(id="inspector")
        Row(
            children=[by_id("tab_view", TabView), by_id("inspector", InspectorPanel)],
            widths=["flex", 0],
            id="body_row",
        )

        CommandPalette(
            on_execute=self._on_palette_execute,
            on_dismiss=self._dismiss_palette,
            id="palette",
        )

        return Column(
            children=[
                by_id("header"),
                by_id("body_row", Row),
                by_id("footer", AppFooter),
            ],
            heights=[2, "flex", 2],
        )

    def setup_root(self, root: ComponentRoot) -> None:
        self._help_panel = HelpPanel(
            entries_source=by_id("tab_view", TabView),
            key_fg=THEME.accent_blue,
        )
        self._help_popup = Popup(
            self._help_panel,
            exit_key=keys.KEY_ESC,
        )
        self._loop.set_input_timeouts(0.125)

    def after_start(self):
        size = self._loop.get_term_size()
        if size.columns < 65 or size.lines < 10:
            self._loop.quit("No enough space to running.")

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

    def toggle_help(self):
        """Toggle help popup visibility. Entries are refreshed automatically
        via HelpPanel.on_before_show before opening."""
        self._help_popup.toggle()

    def toggle_palette(self):
        """Toggle command palette visibility."""
        if self._root is None:
            return
        palette_widget = by_id("palette", CommandPalette)
        if palette_widget is None:
            return
        if palette_widget.is_active:
            palette_widget.close()
        else:
            palette_widget.open()
            self._root.show_sheet(palette_widget, height=8)

    def _dismiss_palette(self) -> None:
        """Dismiss the palette sheet from the root."""
        if self._root is not None:
            self._root.dismiss_sheet()

    def _inspector_width(self, total_width: int) -> int:
        """Compute inspector width: 30% of total, capped at 45."""
        return min(int(total_width * 0.3), 45)

    def toggle_inspector(self):
        """Toggle inspector panel visibility."""
        self._inspector_visible = not self._inspector_visible
        size = self._loop.get_term_size()
        body_row = by_id("body_row", Row)
        inspector = by_id("inspector", InspectorPanel)
        tab_view = by_id("tab_view", TabView)
        if self._inspector_visible:
            body_row.set_widths(["flex", self._inspector_width(size.columns)])
            inspector.update_from(tab_view.active)
        else:
            body_row.set_widths(["flex", 0])
        self._root.resize(size)

    def resize(self, size: tuple[int, int]) -> None:
        """Recompute inspector width on terminal resize."""
        if self._inspector_visible:
            body_row = by_id("body_row", Row)
            if body_row is not None:
                body_row.set_widths(["flex", self._inspector_width(size[0])])
        super().resize(size)

    def goto_status(self):
        by_id("tab_view", TabView).route_to("status")

    def goto_branch(self):
        by_id("tab_view", TabView).route_to("branch")

    def goto_commit(self):
        by_id("tab_view", TabView).route_to("commit")

    def on_event(self, action: ActionEventType, **data) -> bool:
        """Central event router: all panel events bubble up to here."""
        if action is ActionEventType.mode_changed:
            self._header_state.mode = data.get("mode", "")
            return True
        if action is ActionEventType.action_requested:
            if data.get("cmd") == "merge":
                self._on_merge_request(data["source"], data["target"])
                return True
        if action is ActionEventType.selection_changed:
            inspector = by_id("inspector", InspectorPanel)
            tab_view = by_id("tab_view", TabView)
            if inspector is not None and tab_view is not None:
                inspector.update_from(tab_view.active)
            return True
        return False

    def _on_palette_execute(self, cmd: str) -> None:
        """Handle command palette execution."""
        lower = cmd.lower()
        tab_view = by_id("tab_view", TabView)
        if lower == "quit":
            self.quit()
        elif tab_view.route_to(lower) is not None:
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
                    by_id("tab_view", TabView).route_to("status")
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
            by_id("tab_view", TabView).route_to("branch")
            by_id("branch", BranchPanel).refresh()
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

    def quit(self):
        raise ExitEventLoop("Quit")
