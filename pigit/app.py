from time import sleep
from typing import Optional

from .git.repo import GitFileT, GitFuncT, Repo
from .termui import (
    ActionLiteral,
    AlertDialog,
    AppEventLoop,
    bind_keys,
    Container,
    GitPanelLazyResizeMixin,
    HelpPanel,
    ItemSelector,
    LineTextBrowser,
    OverlayHostMixin,
    OverlayKind,
    Popup,
    keys,
)

repo_handle = Repo()


def _noop_alert_result(_: bool) -> None:
    """Placeholder until :meth:`~pigit.termui.components_overlay.AlertDialog.alert` supplies a callback."""


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

        self._alert_dialog = AlertDialog(
            self,
            x=x,
            y=y,
            size=size,
            inner_width=alert_inner_width,
            on_result=_noop_alert_result,
        )
        self._alert_popup = self._alert_dialog

    @bind_keys("j")
    def next(self, step: int = 1) -> None:
        super().next(step)

    @bind_keys("k")
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
        self._alert_popup.resize(size)

    def on_key(self, key: str):
        if not self.files:
            return
        f = self.files[self.curr_no]

        if key == keys.KEY_ENTER:
            c = self.git.load_file_diff(f.name, f.tracked, f.has_staged_change).split(
                "\n"
            )
            self.emit(
                "goto", target="display_panel", source=self.NAME, key=f.name, content=c
            )
            return
        elif key in {keys.KEY_SPACE, "a"}:
            self.git.switch_file_status(f)
        elif key == "i":
            if self._check_via_alert(self.git.ignore_file, f, msg="Ignore file"):
                return
        elif key == "d":
            if self._check_via_alert(self.git.discard_file, f, msg="Discard file"):
                return

        self.fresh()

    def _check_via_alert(
        self,
        callee: GitFuncT,
        file: GitFileT,
        msg: str = "",
    ) -> bool:
        """
        Ask for confirmation via this panel's :class:`~pigit.termui.components_overlay.AlertDialog`.

        Returns:
            True if the dialog was shown (caller should skip its own refresh).
            False if the root cannot host an alert session (no-op).
        """

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
        if key == "enter":
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

    def update(self, action: ActionLiteral, **data):
        if action == "goto":
            self.i_cache[self.i_cache_key] = self._i

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


class GitTuiRoot(OverlayHostMixin, Container):
    """Git full-screen root: tabbed panels plus one overlay (help or alert)."""

    NAME = "container"

    def __init__(
        self,
        *,
        help_popup_width: Optional[int] = None,
        help_popup_height: Optional[int] = None,
        help_offset: Optional[tuple[int, int]] = None,
        alert_inner_width: Optional[int] = None,
    ) -> None:
        status_panel = StatusPanel(alert_inner_width=alert_inner_width)
        branch_panel = BranchPanel()
        commit_panel = CommitPanel()
        display_panel = ContentDisplay()

        children = {
            status_panel.NAME: status_panel,
            branch_panel.NAME: branch_panel,
            commit_panel.NAME: commit_panel,
            display_panel.NAME: display_panel,
        }

        def get_name(key: str):
            return {
                "1": status_panel.NAME,
                "2": branch_panel.NAME,
                "3": commit_panel.NAME,
            }.get(key, "")

        Container.__init__(
            self,
            children,
            start_name=status_panel.NAME,
            switch_handle=get_name,
        )

        self._init_overlay_host_state()
        self._help_panel = HelpPanel(
            inner_width=help_popup_width,
            inner_height=help_popup_height,
        )
        self._help_popup = Popup(
            self._help_panel,
            session_owner=self,
            offset=help_offset,
            exit_key=keys.KEY_ESC,
        )

    @bind_keys("?")
    def _toggle_help_popup(self) -> None:
        help_open = (
            self.overlay_kind == OverlayKind.POPUP
            and self._active_popup is self._help_popup
        )
        if not help_open:
            self._help_panel.merge_help_entries_from_host_children(self)
        self._help_popup.toggle()

    def _handle_event(self, key: str) -> None:
        handler = self._key_handlers.get(key)
        if handler is not None:
            handler()
            return
        super()._handle_event(key)

    def resize(self, size: tuple[int, int]) -> None:
        super().resize(size)
        self._help_popup.resize(size)


class App(AppEventLoop):
    BINDINGS = [
        ("Q", "quit"),
    ]

    def __init__(self) -> None:
        super().__init__(
            GitTuiRoot(),
            input_takeover=True,
        )

        self.set_input_timeouts(0.125)

    def after_start(self):
        if self._size.columns < 65 or self._size.lines < 10:
            self.quit("No enough space to running.")
