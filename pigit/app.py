# -*- coding: utf-8 -*-
"""
Module: pigit/app.py
Description: Git TUI panels and application entry.
Author: Zev
Date: 2026-04-17
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional, Union

from pigit.termui import (
    AlertDialog,
    Application,
    Column,
    Component,
    ComponentRoot,
    exec_external,
    ExitEventLoop,
    get_badge,
    Header,
    HelpPanel,
    hide_spinner,
    keys,
    palette,
    Popup,
    Row,
    Segment,
    show_spinner,
    show_toast,
    Signal,
    TabView,
    ToastPosition,
)
from pigit.git.local_git import GitError
from .app_branch import BranchPanel
from .app_chrome import AppFooter
from .app_commit import CommitPanel
from .app_diff import DiffViewer
from .app_inspector import InspectorPanel
from .app_command_palette import CommandPalette
from .app_status import StatusPanel
from .app_theme import THEME
from .git.repo import Repo


@dataclass
class _PigitWidgets:
    """Container for all major UI widgets created in build_root()."""

    header: Header
    footer: AppFooter
    tab_view: TabView
    body_row: Row
    palette: CommandPalette
    inspector: InspectorPanel
    status: StatusPanel
    branch: BranchPanel
    commit: CommitPanel
    diff: DiffViewer


class PigitApplication(Application):
    """Pigit TUI application entry."""

    BINDINGS = [
        ("Q", "quit"),
        ("?", "toggle_help"),
        (";", "toggle_palette"),
        ("I", "toggle_inspector"),
    ]

    def __init__(self, repo: Optional[Repo] = None) -> None:
        super().__init__(input_takeover=True)
        self._repo = repo or Repo()
        self._repo_path, self._repo_conf = self._repo.confirm_repo()
        self._git = self._repo.bind_path(self._repo_path)
        self._widgets: Optional[_PigitWidgets] = None
        self._inspector_visible = False
        # Header state
        self._repo_name: str = ""
        self._branch_signal: Signal[str] = Signal("")
        self._ahead: int = 0
        self._behind: int = 0
        self._current_tab: str = "Status"
        self._current_tab_key: str = "1"
        self._mode: str = ""
        # Merge workflow state
        self._merge_state: Optional[dict] = None
        self._alert_dialog = AlertDialog(
            inner_width=50,
            on_result=lambda _: None,
        )

    def build_root(self) -> Component:
        diff_viewer = DiffViewer()
        status_panel = StatusPanel(
            display=diff_viewer,
            on_visual_mode_changed=self._on_visual_mode_changed,
            on_selection_changed=self._on_panel_selection_changed,
            git=self._git,
        )
        branch_panel = BranchPanel(
            on_selection_changed=self._on_panel_selection_changed,
            branch_signal=self._branch_signal,
            git=self._git,
            on_merge_request=self._on_merge_request,
        )
        commit_panel = CommitPanel(
            display=diff_viewer,
            on_selection_changed=self._on_panel_selection_changed,
            git=self._git,
        )

        _GLOBAL_HELP: list[tuple[str, str]] = [
            ("Q", "Quit"),
            ("I", "Inspector"),
            (";", "Palette"),
        ]
        _TAB_LABELS: dict[Component, str] = {
            status_panel: "Status",
            branch_panel: "Branch",
            commit_panel: "Commit",
            diff_viewer: "Display",
        }
        _TAB_KEYS: dict[Component, str] = {
            status_panel: "1",
            branch_panel: "2",
            commit_panel: "3",
            diff_viewer: "",
        }

        header = Header(
            separator=True,
            sep_fg=THEME.fg_dim,
            on_refresh=self._refresh_header,
        )
        footer = AppFooter(theme=THEME)
        footer.set_global_help(_GLOBAL_HELP)

        def _on_tab_switch(panel: Component) -> None:
            provider = getattr(panel, "get_help_entries", None)
            footer.set_help_provider(provider)
            self._current_tab = _TAB_LABELS.get(panel, "")
            self._current_tab_key = _TAB_KEYS.get(panel, "")
            self._w.inspector.update_from(panel)

        tab_view = TabView(
            children=[status_panel, branch_panel, commit_panel, diff_viewer],
            shortcuts={
                "1": status_panel,
                "2": branch_panel,
                "3": commit_panel,
            },
            start=status_panel,
            on_switch=_on_tab_switch,
        )
        provider = getattr(tab_view.active, "get_help_entries", None)
        footer.set_help_provider(provider)

        palette = CommandPalette(
            on_execute=self._on_palette_execute,
            on_dismiss=self._dismiss_palette,
        )

        inspector = InspectorPanel()
        body_row = Row(
            children=[tab_view, inspector],
            widths=["flex", 0],
        )

        self._widgets = _PigitWidgets(
            header=header,
            footer=footer,
            tab_view=tab_view,
            body_row=body_row,
            palette=palette,
            inspector=inspector,
            status=status_panel,
            branch=branch_panel,
            commit=commit_panel,
            diff=diff_viewer,
        )

        chrome_column = Column(
            children=[header, body_row, footer],
            heights=[2, "flex", 2],
        )
        return chrome_column

    @property
    def _w(self) -> _PigitWidgets:
        """Shorthand for accessing widgets; raises if build_root() has not run."""
        assert self._widgets is not None
        return self._widgets

    def setup_root(self, root: ComponentRoot) -> None:
        self._help_panel = HelpPanel(
            entries_source=self._w.tab_view,
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
            self._branch_signal.set(head)
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

    def _on_visual_mode_changed(self, mode: str) -> None:
        self._mode = mode

    def _refresh_header(self, header: Header) -> None:
        badge, badge_bg, badge_fg = get_badge()
        left: list[Segment] = []
        if badge:
            left.append(
                Segment(
                    f"{badge} ",
                    fg=badge_fg or THEME.fg_primary,
                    style_flags=palette.STYLE_BOLD,
                )
            )
        left.extend(
            [
                Segment(self._repo_name, fg=THEME.fg_primary),
                Segment("  ", fg=THEME.fg_dim),
                Segment(self._branch_signal.value, fg=THEME.accent_cyan),
            ]
        )

        center: list[Segment] = []
        if self._ahead > 0:
            center.append(Segment(f"\u2191{self._ahead} ", fg=THEME.accent_green))
        if self._behind > 0:
            center.append(Segment(f"\u2193{self._behind}", fg=THEME.accent_yellow))

        right: list[Segment] = []
        if self._merge_state:
            target = self._merge_state.get("target", "")
            right.append(
                Segment(
                    f"[MERGE] {target}  ",
                    fg=THEME.accent_red,
                    style_flags=palette.STYLE_BOLD,
                )
            )
        if self._mode:
            right.append(
                Segment(
                    f"[{self._mode}]  ",
                    fg=THEME.fg_primary,
                    style_flags=palette.STYLE_BOLD,
                )
            )
        right.append(
            Segment(
                self._current_tab, fg=THEME.fg_muted, style_flags=palette.STYLE_BOLD
            )
        )
        if self._current_tab_key:
            right.append(
                Segment(
                    f" [{self._current_tab_key}]",
                    fg=THEME.fg_primary,
                    style_flags=palette.STYLE_BOLD,
                )
            )

        header.set_left(left)
        header.set_center(center)
        header.set_right(right)

    def _on_panel_selection_changed(self, idx: int) -> None:
        """Callback when panel selection changes via j/k navigation."""
        if self._widgets is not None:
            self._w.inspector.update_from(self._w.tab_view.active)

    def toggle_help(self):
        """Toggle help popup visibility. Entries are refreshed automatically
        via HelpPanel.on_before_show before opening."""
        self._help_popup.toggle()

    def toggle_palette(self):
        """Toggle command palette visibility."""
        if self._widgets is None or self._root is None:
            return
        if self._w.palette.is_active:
            self._w.palette.close()
        else:
            self._w.palette.open()
            self._root.show_sheet(self._w.palette, height=8)

    def _dismiss_palette(self) -> None:
        """Dismiss the palette sheet from the root."""
        if self._root is not None:
            self._root.dismiss_sheet()

    def _inspector_width(self, total_width: int) -> int:
        """Compute inspector width: 30% of total, capped at 45."""
        return min(int(total_width * 0.3), 45)

    def toggle_inspector(self):
        """Toggle inspector panel visibility."""
        if self._widgets is None:
            return
        self._inspector_visible = not self._inspector_visible
        size = self._loop.get_term_size()
        if self._inspector_visible:
            self._w.body_row.set_widths(["flex", self._inspector_width(size.columns)])
            self._w.inspector.update_from(self._w.tab_view.active)
        else:
            self._w.body_row.set_widths(["flex", 0])
        self._root.resize(size)

    def resize(self, size: tuple[int, int]) -> None:
        """Recompute inspector width on terminal resize."""
        if self._inspector_visible and self._widgets is not None:
            self._w.body_row.set_widths(["flex", self._inspector_width(size[0])])
        super().resize(size)

    def _on_palette_execute(self, cmd: str) -> None:
        """Handle command palette execution."""
        if self._widgets is None:
            return
        lower = cmd.lower()
        cmd_map: dict[str, Optional[Union[Component, str]]] = {
            "status": self._w.status,
            "branch": self._w.branch,
            "commit": self._w.commit,
            "diff": self._w.diff,
            "quit": "quit",
        }
        target = cmd_map.get(lower)
        if target == "quit":
            self.quit()
        elif target is not None:
            self._w.tab_view.route_to(target)
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

    def _load_merge_state(self) -> Optional[dict]:
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
            show_toast(
                f"Resume merge: {state['source']} \u2192 {state['target']} (continue-merge)",
                duration=3.0,
            )
        else:
            self._clear_merge_state()

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
                    self._save_merge_state(source, target)
                    show_toast(
                        "Conflict! Resolve in Status, then continue-merge",
                        duration=3.0,
                    )
                    self._w.tab_view.route_to(self._w.status)
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
            self._clear_merge_state()
            self._w.tab_view.route_to(self._w.branch)
            self._w.branch.refresh()
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
