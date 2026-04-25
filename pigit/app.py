# -*- coding: utf-8 -*-
"""
Module: pigit/app.py
Description: Git TUI panels and application entry.
Author: Zev
Date: 2026-04-17
"""

import logging
import os
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import subprocess

from pigit.termui import (
    Application,
    Column,
    Component,
    ComponentRoot,
    ExitEventLoop,
    HelpPanel,
    keys,
    LayerKind,
    Popup,
    Row,
    TabView,
    ToastPosition,
)
from .app_branch import BranchPanel
from .app_chrome import AppFooter, AppHeader, PeekLabel
from .app_commit import CommitPanel
from .app_diff import DiffViewer
from .app_inspector import InspectorPanel
from .app_palette import CommandPalette
from .app_status import StatusPanel
from .app_theme import THEME
from .git.repo import Repo

repo_handle = Repo()

ExternalProcessCallback = Callable[
    [list[str], Optional[str]],
    "subprocess.CompletedProcess[str]",
]


class PigitApplication(Application):
    """Pigit TUI application entry."""

    BINDINGS = [
        ("Q", "quit"),
        ("?", "toggle_help"),
        (";", "toggle_palette"),
        ("I", "toggle_inspector"),
    ]

    def __init__(self) -> None:
        super().__init__(input_takeover=True)
        self._header: Optional[AppHeader] = None
        self._footer: Optional[AppFooter] = None
        self._tab_view: Optional[TabView] = None
        self._body_row: Optional[Row] = None
        self._peek_label = PeekLabel()
        self._repo_path: Optional[str] = None
        self._palette: Optional[CommandPalette] = None
        self._inspector: Optional[InspectorPanel] = None
        self._inspector_visible = False

    def build_root(self):
        display_panel = DiffViewer()
        status_panel = StatusPanel(
            on_shell=self.on_shell_request,
            display=display_panel,
            on_visual_mode_changed=self._on_visual_mode_changed,
            on_selection_changed=self._on_panel_selection_changed,
            on_badge=self._show_status_badge,
        )
        branch_panel = BranchPanel(
            on_selection_changed=self._on_panel_selection_changed,
        )
        commit_panel = CommitPanel(
            display=display_panel,
            on_selection_changed=self._on_panel_selection_changed,
        )

        _TAB_HELP: dict[Component, list[tuple[str, str]]] = {
            status_panel: [
                ("j/k", "Navigate"),
                ("Enter", "Open"),
                ("a", "Stage"),
                ("d", "Discard"),
                ("i", "Ignore"),
                ("v", "Visual"),
                ("?", "Help"),
            ],
            branch_panel: [
                ("j/k", "Navigate"),
                ("Enter/Space", "Checkout"),
                ("?", "Help"),
            ],
            commit_panel: [
                ("j/k", "Navigate"),
                ("Enter", "View"),
                ("g", "Toggle view"),
                ("?", "Help"),
            ],
            display_panel: [
                ("j/k", "Navigate"),
                 ("J/K", "Quick Navigate"),
                ("esc", "Back"),
                ("?", "Help"),
            ],
        }
        _TAB_LABELS: dict[Component, str] = {
            status_panel: "Status",
            branch_panel: "Branch",
            commit_panel: "Commit",
            display_panel: "Display",
        }
        _TAB_KEYS: dict[Component, str] = {
            status_panel: "1",
            branch_panel: "2",
            commit_panel: "3",
            display_panel: "",
        }

        def _on_tab_switch(panel: Component) -> None:
            self._footer.set_context("", _TAB_HELP.get(panel, []))
            self._header.set_state(
                current_tab=_TAB_LABELS.get(panel, ""),
                current_tab_key=_TAB_KEYS.get(panel, ""),
            )
            self._update_inspector_content()

        self._tab_view = TabView(
            children=[status_panel, branch_panel, commit_panel, display_panel],
            shortcuts={
                "1": status_panel,
                "2": branch_panel,
                "3": commit_panel,
            },
            start=status_panel,
            on_switch=_on_tab_switch,
        )
        self._status_panel = status_panel
        self._branch_panel = branch_panel
        self._commit_panel = commit_panel
        self._display_panel = display_panel

        self._header = AppHeader(
            theme=THEME,
            repo_name="",
            branch_name="",
            current_tab="Status",
            current_tab_key="1",
        )
        self._footer = AppFooter(theme=THEME)
        self._footer.set_context(
            "",
            (
                _TAB_HELP.get(self._tab_view.active, [])
                if self._tab_view is not None
                else []
            ),
        )

        # Command palette
        self._palette = CommandPalette(
            on_execute=self._on_palette_execute,
            on_dismiss=self._dismiss_palette,
        )

        self._inspector = InspectorPanel()
        self._body_row = Row(
            children=[self._tab_view, self._inspector],
            widths=["flex", 0],
        )

        chrome_column = Column(
            children=[self._header, self._body_row, self._footer],
            heights=[2, "flex", 2],
        )
        return chrome_column

    def setup_root(self, root: ComponentRoot) -> None:
        self._help_panel = HelpPanel()
        self._help_popup = Popup(
            self._help_panel,
            session_owner=root,
            exit_key=keys.KEY_ESC,
        )
        self._loop.set_input_timeouts(0.125)

    def after_start(self):
        size = self._loop.get_term_size()
        if size.columns < 65 or size.lines < 10:
            self._loop.quit("No enough space to running.")

        # Initialize header with repo info
        try:
            repo_path, _ = repo_handle.confirm_repo()
            self._repo_path = repo_path
            git = repo_handle.bind_path(repo_path)
            head = git.get_head() or ""
            self._header.set_state(
                repo_name=os.path.basename(repo_path) if repo_path else "",
                branch_name=head,
            )
        except Exception:
            logging.warning("Failed to initialize repo info", exc_info=True)
            self._root.show_toast(
                "Failed to load repo info. Check git configuration.",
                duration=3.0,
                position=ToastPosition.BOTTOM_LEFT,
            )

        self._root.show_toast(
            "Welcome to Pigit! Press ? for help.",
            duration=3.0,
            position=ToastPosition.BOTTOM_LEFT,
        )

    def on_shell_request(self, cmd: list[str], cwd: Optional[str] = None):
        result = self.run_external_process(cmd, cwd=cwd)
        if result.returncode == 0:
            self._refresh_status_panel()
        return result

    def _refresh_status_panel(self) -> None:
        status = getattr(self, "_status_panel", None)
        if status is not None and hasattr(status, "fresh"):
            status.fresh()

    def _on_visual_mode_changed(self, mode: str) -> None:
        if self._header is not None:
            self._header.set_state(mode=mode)

    def _on_panel_selection_changed(self, idx: int) -> None:
        """Callback when panel selection changes via j/k navigation."""
        self._update_inspector_content()

    def _show_status_badge(self, msg: str) -> None:
        """Show a transient badge in the header for 1.5s."""
        if self._root is not None:
            self._root.show_badge(
                msg,
                duration=1.5,
                bg=THEME.bg_active,
                fg=THEME.fg_primary,
            )

    def toggle_help(self):
        root = self._root
        assert isinstance(root, ComponentRoot)

        help_open = root._layer_stack.top(LayerKind.MODAL) is self._help_popup
        if not help_open:
            # Help panel merges from the TabView inside Column
            tab_view = self._tab_view
            if tab_view is not None:
                self._help_panel.merge_help_entries_from_host_children(tab_view)
        self._help_popup.toggle()

    def toggle_palette(self):
        """Toggle command palette visibility."""
        if self._palette is None or self._root is None:
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

    def toggle_inspector(self):
        """Toggle inspector panel visibility."""
        if self._inspector is None or self._body_row is None:
            return
        self._inspector_visible = not self._inspector_visible
        size = self._loop.get_term_size()
        if self._inspector_visible:
            self._body_row.set_widths(
                ["flex", self._inspector_width(size.columns)]
            )
            self._update_inspector_content()
        else:
            self._body_row.set_widths(["flex", 0])
        self._root.resize(size)

    def resize(self, size: tuple[int, int]) -> None:
        """Recompute inspector width on terminal resize."""
        if self._inspector_visible and self._body_row is not None:
            self._body_row.set_widths(
                ["flex", self._inspector_width(size[0])]
            )
        super().resize(size)

    def _update_inspector_content(self):
        """Update inspector based on current tab and selection."""
        if self._inspector is None or self._tab_view is None:
            return
        active = self._tab_view.active
        if active is None:
            return
        idx = getattr(active, "curr_no", 0)
        # Skip if neither panel nor selection has changed
        last = getattr(self, "_last_inspector_key", None)
        current_key = (id(active), idx)
        if last == current_key:
            return
        self._last_inspector_key = current_key

        status = getattr(self, "_status_panel", None)
        branch = getattr(self, "_branch_panel", None)
        commit = getattr(self, "_commit_panel", None)
        git = getattr(active, "git", None)

        if active is status and hasattr(active, "files"):
            files = active.files
            if files and 0 <= idx < len(files):
                file = files[idx]
                size, mtime = ("?", "?")
                if git is not None:
                    size, mtime = git.get_file_info(file)
                self._inspector.show_file(file, size=size, mtime=mtime)
        elif active is branch and hasattr(active, "branches"):
            branches = active.branches
            if branches and 0 <= idx < len(branches):
                b = branches[idx]
                recent_msg, recent_author, created = "?", "?", "?"
                if git is not None:
                    recent_msg, recent_author = git.get_branch_recent_commit(b.name)
                    created = git.get_branch_creation_time(b.name)
                self._inspector.show_branch(
                    b,
                    recent_msg=recent_msg,
                    recent_author=recent_author,
                    created=created,
                )
        elif active is commit and hasattr(active, "commits"):
            commits = active.commits
            if commits and 0 <= idx < len(commits):
                c = commits[idx]
                changed_files, total_add, total_del = [], 0, 0
                if git is not None:
                    changed_files, total_add, total_del = git.get_commit_stats(c.sha)
                self._inspector.show_commit(
                    c,
                    changed_files=changed_files,
                    total_add=total_add,
                    total_del=total_del,
                )

    def _on_palette_execute(self, cmd: str) -> None:
        """Handle command palette execution."""
        cmd_map = {
            "status": getattr(self, "_status_panel", None),
            "branch": getattr(self, "_branch_panel", None),
            "commit": getattr(self, "_commit_panel", None),
            "diff": getattr(self, "_display_panel", None),
            "quit": "quit",
        }
        target = cmd_map.get(cmd.lower())
        if target == "quit":
            self.quit()
        elif target is not None and self._tab_view is not None:
            self._tab_view.route_to(target)

    def quit(self):
        raise ExitEventLoop("Quit")
