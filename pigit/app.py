# -*- coding: utf-8 -*-
"""
Module: pigit/app.py
Description: Git TUI panels and application entry.
Author: Zev
Date: 2026-04-17
"""

from time import sleep
from typing import Optional

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
)
from .git.repo import GitFileT, GitFuncT, Repo

repo_handle = Repo()


def _noop_alert_result(_: bool) -> None:
    pass


class StatusPanel(GitPanelLazyResizeMixin, ItemSelector):
    NAME = "status"

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        content: Optional[list[str]] = None,
        *,
        alert_inner_width: Optional[int] = None,
    ) -> None:
        super().__init__(x, y, size, content)
        self.repo_path, self.repo_conf = repo_handle.confirm_repo()
        self.git = repo_handle.bind_path(self.repo_path)

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
            c = self.git.load_file_diff(f.name, f.tracked, f.has_staged_change).split("\n")
            self.emit(
                "goto", target="display_panel", source=self.NAME, key=f.name, content=c
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


class BranchPanel(GitPanelLazyResizeMixin, ItemSelector):
    NAME = "branch"

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
        if key == keys.KEY_SPACE:
            local_branch = self.branches[self.curr_no]
            if local_branch.is_head:
                return
            err = self.git.checkout_branch(local_branch.name)
            if "error" in err:
                print(err, sep="", flush=True)
                sleep(2)
            self.fresh()


class CommitPanel(GitPanelLazyResizeMixin, ItemSelector):
    NAME = "commit"

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
            self.emit("goto", target="display_panel", source=self.NAME, content=content)


class ContentDisplay(LineTextBrowser):
    NAME = "display_panel"

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size, "")
        self.come_from = ""
        self.i_cache_key = ""
        self.i_cache = {}

    def fresh(self):
        pass

    _CACHE_MAX = 64

    def update(self, action: ActionLiteral, **data):
        if action == "goto":
            self.i_cache[self.i_cache_key] = self._i
            if len(self.i_cache) > self._CACHE_MAX:
                # Simple FIFO eviction: drop oldest half.
                keys_to_drop = list(self.i_cache.keys())[: self._CACHE_MAX // 2]
                for k in keys_to_drop:
                    del self.i_cache[k]
            self.come_from = data.get("source", "")
            self.i_cache_key = data.get("key", "")
            self._content = data.get("content", "")
            self._i = self.i_cache.get(self.i_cache_key, 0)

    @bind_keys("esc", "q")
    def _leave_display(self) -> None:
        self.emit("goto", target=self.come_from)

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
        status_panel = StatusPanel()
        branch_panel = BranchPanel()
        commit_panel = CommitPanel()
        display_panel = ContentDisplay()

        def get_name(key: str):
            return {
                "1": status_panel.NAME,
                "2": branch_panel.NAME,
                "3": commit_panel.NAME,
            }.get(key, "")

        return TabView(
            {
                status_panel.NAME: status_panel,
                branch_panel.NAME: branch_panel,
                commit_panel.NAME: commit_panel,
                display_panel.NAME: display_panel,
            },
            start_name=status_panel.NAME,
            switch_handle=get_name,
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
        self._root.show_toast("Welcome to Pigit! Press ? for help.", duration=3.0, position=ToastPosition.BOTTOM_LEFT)

    def toggle_help(self):
        root = self._root
        assert isinstance(root, ComponentRoot)

        help_open = root._layer_stack.top(LayerKind.MODAL) is self._help_popup
        if not help_open:
            self._help_panel.merge_help_entries_from_host_children(root.body)
        self._help_popup.toggle()

    def quit(self):
        raise ExitEventLoop("Quit")
