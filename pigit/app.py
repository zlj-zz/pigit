# -*- coding: utf-8 -*-
"""
Module: pigit/app.py
Description: Git TUI panels and application entry.
Author: Zev
Date: 2026-04-17
"""

import logging
import os
from dataclasses import dataclass
from typing import Callable, Optional, TYPE_CHECKING, Union

from pigit.termui import (
    Application,
    Column,
    Component,
    ComponentRoot,
    ExitEventLoop,
    get_badge,
    Header,
    HelpPanel,
    keys,
    LayerKind,
    Popup,
    Row,
    show_toast,
    TabView,
    ToastPosition,
)
from pigit.termui._reactive import Signal
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
            self._update_inspector_content()

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

    def _on_visual_mode_changed(self, mode: str) -> None:
        self._mode = mode

    def _refresh_header(self, header: Header) -> None:
        badge, badge_bg, badge_fg = get_badge()
        left: list[tuple[str, tuple[int, int, int], bool]] = []
        if badge:
            left.append((f"{badge} ", badge_fg or THEME.fg_primary, True))
        left.extend(
            [
                (self._repo_name, THEME.fg_primary, False),
                ("  ", THEME.fg_dim, False),
                (self._branch_signal.value, THEME.accent_cyan, False),
            ]
        )

        center: list[tuple[str, tuple[int, int, int], bool]] = []
        if self._ahead > 0:
            center.append((f"\u2191{self._ahead} ", THEME.accent_green, False))
        if self._behind > 0:
            center.append((f"\u2193{self._behind}", THEME.accent_yellow, False))

        right: list[tuple[str, tuple[int, int, int], bool]] = []
        if self._mode:
            right.append((f"[{self._mode}]  ", THEME.fg_primary, True))
        right.append((self._current_tab, THEME.fg_muted, True))
        if self._current_tab_key:
            right.append((f" [{self._current_tab_key}]", THEME.fg_primary, True))

        header.set_left(left)
        header.set_center(center)
        header.set_right(right)

    def _on_panel_selection_changed(self, idx: int) -> None:
        """Callback when panel selection changes via j/k navigation."""
        self._update_inspector_content()

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
            self._update_inspector_content()
        else:
            self._w.body_row.set_widths(["flex", 0])
        self._root.resize(size)

    def resize(self, size: tuple[int, int]) -> None:
        """Recompute inspector width on terminal resize."""
        if self._inspector_visible and self._widgets is not None:
            self._w.body_row.set_widths(["flex", self._inspector_width(size[0])])
        super().resize(size)

    def _update_inspector_content(self):
        """Update inspector based on current tab and selection."""
        if self._widgets is None:
            return
        active = self._w.tab_view.active
        if active is None or not hasattr(active, "get_inspector_data"):
            return
        idx = getattr(active, "curr_no", 0)
        # Skip if neither panel nor selection has changed
        last = getattr(self, "_last_inspector_key", None)
        current_key = (id(active), idx)
        if last == current_key:
            return
        self._last_inspector_key = current_key
        self._w.inspector.show(active.get_inspector_data())

    def _on_palette_execute(self, cmd: str) -> None:
        """Handle command palette execution."""
        if self._widgets is None:
            return
        cmd_map: dict[str, Optional[Union[Component, str]]] = {
            "status": self._w.status,
            "branch": self._w.branch,
            "commit": self._w.commit,
            "diff": self._w.diff,
            "quit": "quit",
        }
        target = cmd_map.get(cmd.lower())
        if target == "quit":
            self.quit()
        elif target is not None:
            self._w.tab_view.route_to(target)

    def quit(self):
        raise ExitEventLoop("Quit")
