# -*- coding: utf-8 -*-
"""
Module: pigit/app.py
Description: Git TUI panels and application entry.
Author: Zev
Date: 2026-04-17
"""

from enum import Enum
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import subprocess

from pigit.termui import (
    ActionLiteral,
    AlertDialog,
    Application,
    bind_keys,
    ComponentRoot,
    ExitEventLoop,
    GitPanelLazyResizeMixin,
    HelpPanel,
    ItemSelector,
    keys,
    LayerKind,
    LineTextBrowser,
    Popup,
    TabView,
    ToastPosition,
    OverlayClientMixin,
)
from .git.repo import GitFileT, GitFuncT, Repo

repo_handle = Repo()

ExternalProcessCallback = Callable[
    [list[str], Optional[str]],
    "subprocess.CompletedProcess[str]",
]


class PanelRoute(str, Enum):
    """Type-safe route identifiers for Pigit TUI panels."""

    STATUS = "/status"
    BRANCH = "/branch"
    COMMIT = "/commit"
    DISPLAY = "/display"


def _noop_alert_result(_: bool) -> None:
    pass


class StatusPanel(GitPanelLazyResizeMixin, ItemSelector, OverlayClientMixin):
    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        content: Optional[list[str]] = None,
        *,
        alert_inner_width: Optional[int] = None,
        on_shell: Optional[ExternalProcessCallback] = None,
    ) -> None:
        super().__init__(x, y, size, content)
        self.repo_path, self.repo_conf = repo_handle.confirm_repo()
        self.git = repo_handle.bind_path(self.repo_path)
        self._on_shell = on_shell

        self.files: list[GitFileT] = []
        self._alert_dialog = AlertDialog(
            self,
            x=x,
            y=y,
            size=size,
            inner_width=alert_inner_width,
            on_result=_noop_alert_result,
        )

    @bind_keys("j", keys.KEY_DOWN)
    def next(self, step: int = 1) -> None:
        super().next(step)

    @bind_keys("k", keys.KEY_UP)
    def forward(self, step: int = 1) -> None:
        super().forward(step)

    def fresh(self):
        self.files = files = self.git.load_status(self._size[0])
        if not files:
            self.set_content(["No status changed."])
            return
        files_str = [file.display_str for file in files]
        self.set_content(files_str)

    def resize(self, size: tuple[int, int]) -> None:
        super().resize(size)
        self._alert_dialog.resize(size)

    def on_key(self, key: str):
        if not self.files:
            return
        f = self.files[self.curr_no]
        if key == keys.KEY_ENTER:
            # MM: prefer unstaged diff; otherwise show staged if exists
            cached = f.has_staged_change and not f.has_unstaged_change
            c = self.git.load_file_diff(f.name, f.tracked, cached).split("\n")
            self.emit(
                ActionLiteral.goto,
                target=PanelRoute.DISPLAY,
                source=PanelRoute.STATUS,
                key=f.name,
                content=c,
            )
            return
        if key in {keys.KEY_SPACE, "a"}:
            self.git.switch_file_status(f)
            self.fresh()
            return
        if key == "i":
            if self._check_via_alert(self.git.ignore_file, f, msg="Ignore file"):
                return
            self.fresh()
            return
        if key == "d":
            if self._check_via_alert(self.git.discard_file, f, msg="Discard file"):
                return
            self.fresh()

    @bind_keys("C")
    def create_commit(self) -> None:
        """Create a new commit with default editor."""
        if not self.git.has_staged_changes(self.repo_path):
            self.show_toast("No staged changes to commit.", duration=2.0)
            return
        if self._on_shell is None:
            self.show_toast("Editor launch is not configured.", duration=2.0)
            return
        try:
            result = self._on_shell(["git", "commit"], self.repo_path)
        except Exception as e:
            self.show_toast(f"Failed to open editor: {e}", duration=3.0)
            return
        if result.returncode != 0:
            self.show_toast(f"Commit failed (exit {result.returncode}).", duration=2.0)

    def _check_via_alert(
        self,
        callee: GitFuncT,
        file: GitFileT,
        msg: str = "",
    ) -> bool:
        text = f"{msg} '{file}' ?"

        def on_result(confirmed: bool) -> None:
            if not confirmed:
                self.fresh()
                return
            callee(file)
            self.fresh()
            if self.files:
                self.curr_no = min(max(self.curr_no, 0), len(self.files) - 1)

        return self._alert_dialog.alert(text, on_result)


class BranchPanel(GitPanelLazyResizeMixin, ItemSelector, OverlayClientMixin):
    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        content: Optional[list[str]] = None,
    ) -> None:
        super().__init__(x, y, size, content)
        self.repo_path, self.repo_conf = repo_handle.confirm_repo()
        self.git = repo_handle.bind_path(self.repo_path)

    def fresh(self):
        self.branches = branches = self.git.load_branches()
        if not branches:
            return ["No status changed."]
        processed_branches = []
        for branch in branches:
            if branch.is_head:
                processed_branches.append(f"* {branch.name}")
            else:
                processed_branches.append(f"  {branch.name}")
        self.set_content(processed_branches)

    @bind_keys("j")
    def next(self, step: int = 1) -> None:
        super().next(step)

    @bind_keys("k")
    def forward(self, step: int = 1) -> None:
        super().forward(step)

    def on_key(self, key: str):
        if key in {keys.KEY_SPACE, keys.KEY_ENTER}:
            local_branch = self.branches[self.curr_no]
            if local_branch.is_head:
                return
            err = self.git.checkout_branch(local_branch.name)
            if "error" in err:
                self.show_toast(f"Checkout failed: {err}", duration=3.0)
            self.fresh()


class CommitPanel(GitPanelLazyResizeMixin, ItemSelector):
    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        content: Optional[list[str]] = None,
    ) -> None:
        super().__init__(x, y, size, content)
        self.repo_path, self.repo_conf = repo_handle.confirm_repo()
        self.git = repo_handle.bind_path(self.repo_path)

    @bind_keys("j")
    def next(self, step: int = 1) -> None:
        super().next(step)

    @bind_keys("k")
    def forward(self, step: int = 1) -> None:
        super().forward(step)

    def fresh(self):
        branch_name = self.git.get_head()
        self.commits = commits = self.git.load_commits(branch_name or "")
        if not commits:
            return ["No status changed."]
        processed_commits = []
        for commit in commits:
            state_flag = "   " if commit.is_pushed() else " ? "
            processed_commits.append(f"{state_flag}{commit.sha[:7]} {commit.msg}")
        self.set_content(processed_commits)

    def on_key(self, key: str):
        if key == keys.KEY_ENTER:
            commit = self.commits[self.curr_no]
            content = self.git.load_commit_info(commit.sha).split("\n")
            self.emit(
                ActionLiteral.goto,
                target=PanelRoute.DISPLAY,
                source=PanelRoute.COMMIT,
                content=content,
            )


class ContentDisplay(LineTextBrowser):
    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size, "")
        self.come_from: PanelRoute | None = None
        self.i_cache_key = ""
        self.i_cache = {}

    def fresh(self):
        pass

    _CACHE_MAX = 64

    def update(self, action: ActionLiteral, **data):
        if action is ActionLiteral.goto:
            self.i_cache[self.i_cache_key] = self._i
            while len(self.i_cache) >= self._CACHE_MAX:
                del self.i_cache[next(iter(self.i_cache))]
            src = data.get("source")
            self.come_from = PanelRoute(src) if isinstance(src, str) and src else None
            self.i_cache_key = data.get("key", "")
            self._content = data.get("content", "")
            self._i = self.i_cache.get(self.i_cache_key, 0)

    @bind_keys("esc", "q")
    def _leave_display(self) -> None:
        if self.come_from is not None:
            self.emit(ActionLiteral.goto, target=self.come_from)

    @bind_keys("j")
    def _scroll_line_down(self) -> None:
        self.scroll_down()

    @bind_keys("k")
    def _scroll_line_up(self) -> None:
        self.scroll_up()

    @bind_keys("J")
    def _scroll_page_down(self) -> None:
        self.scroll_down(5)

    @bind_keys("K")
    def _scroll_page_up(self) -> None:
        self.scroll_up(5)


class PigitApplication(Application):
    """Pigit TUI application entry."""

    BINDINGS = [
        ("Q", "quit"),
        ("?", "toggle_help"),
    ]

    def __init__(self) -> None:
        super().__init__(input_takeover=True)

    def build_root(self):
        status_panel = StatusPanel(on_shell=self.on_shell_request)
        branch_panel = BranchPanel()
        commit_panel = CommitPanel()
        display_panel = ContentDisplay()

        return TabView(
            route_map={
                PanelRoute.STATUS: status_panel,
                PanelRoute.BRANCH: branch_panel,
                PanelRoute.COMMIT: commit_panel,
                PanelRoute.DISPLAY: display_panel,
            },
            shortcuts={
                "1": PanelRoute.STATUS,
                "2": PanelRoute.BRANCH,
                "3": PanelRoute.COMMIT,
            },
            start=PanelRoute.STATUS,
        )

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
        root = self._root
        if root is None:
            return
        body = getattr(root, "body", None)
        if not isinstance(body, TabView):
            return
        status = body.get_tab_by_route(PanelRoute.STATUS)
        if status is not None and hasattr(status, "fresh"):
            status.fresh()

    def toggle_help(self):
        root = self._root
        assert isinstance(root, ComponentRoot)

        help_open = root._layer_stack.top(LayerKind.MODAL) is self._help_popup
        if not help_open:
            self._help_panel.merge_help_entries_from_host_children(root.body)
        self._help_popup.toggle()

    def quit(self):
        raise ExitEventLoop("Quit")
