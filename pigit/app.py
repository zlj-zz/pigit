import logging
from time import sleep
from typing import List, Optional, Tuple

from .git.repo import Repo
from .tui.components import Container, LineTextBrowser, ItemSelector
from .tui.event_loop import EventLoop


_Log = logging.getLogger(f"PIGIT.{__name__}")
repo_handle = Repo()


class StatusPanel(ItemSelector):
    NAME = "status"
    CURSOR = "→"
    BINDINGS = [
        ("j", "next"),
        ("k", "forward"),
    ]

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Tuple[int, int] | None = None,
        content: List[str] | None = None,
    ) -> None:
        super().__init__(x, y, size, content)

        self.repo_path, self.repo_conf = repo_handle.confirm_repo()

    def fresh(self):
        self.files = files = repo_handle.load_status(self._size[0])
        if not files:
            return ["No status changed."]

        files_str = [file.display_str for file in files]
        self.content = files_str

    def on_key(self, key: str):
        f = self.files[self.curr_no]

        if key == "enter":
            c = repo_handle.load_file_diff(
                f.name, f.tracked, f.has_staged_change, path=self.repo_path
            ).split("\n")
            self.emit("goto", target="display_panel", source=self.NAME, key=f.name, content=c)
        elif key in {"a", " "}:
            repo_handle.switch_file_status(f, self.repo_path)
            self.fresh()
            self._render()
        elif key == "i":
            repo_handle.ignore_file(f)
            self.fresh()
            self._render()


class BranchPanel(ItemSelector):
    NAME = "branch"
    CURSOR = "→"

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Tuple[int, int] | None = None,
        content: List[str] | None = None,
    ) -> None:
        super().__init__(x, y, size, content)

        self.repo_path, self.repo_conf = repo_handle.confirm_repo()

    def fresh(self):
        self.branches = branches = repo_handle.load_branches()
        if not branches:
            return ["No status changed."]

        processed_branches = []
        for branch in branches:
            if branch.is_head:
                processed_branches.append(f"* {branch.name}")
            else:
                processed_branches.append(f"  {branch.name}")

        self.content = processed_branches

    def on_key(self, key: str):
        if key == "j":
            self.next()
        elif key == "k":
            self.forward()
        elif key == " ":
            local_branch = self.branches[self.curr_no]
            if local_branch.is_head:
                return

            err = repo_handle.checkout_branch(local_branch.name)
            if "error" in err:
                print(err, sep="", flush=True)
                sleep(2)

            self.fresh()
            self._render()


class CommitPanel(ItemSelector):
    NAME = "commit"
    CURSOR = "→"
    BINDINGS = [
        ("j", "next"),
        ("k", "forward"),
    ]

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Tuple[int, int] | None = None,
        content: List[str] | None = None,
    ) -> None:
        super().__init__(x, y, size, content)

        self.repo_path, self.repo_conf = repo_handle.confirm_repo()

    def fresh(self):
        branch_name = repo_handle.get_head()
        self.commits = commits = repo_handle.load_commits(branch_name)

        if not commits:
            return ["No status changed."]

        processed_commits = []
        for commit in commits:
            state_flag = "   " if commit.is_pushed() else " ? "
            processed_commits.append(f"{state_flag}{commit.sha[:7]} {commit.msg}")

        self.content = processed_commits

    def on_key(self, key: str):
        if key == "enter":
            commit = self.commits[self.curr_no]
            content = repo_handle.load_commit_info(commit.sha).split("\n")
            self.emit("goto", target="display_panel", source=self.NAME, content=content)


class ContentDisplay(LineTextBrowser):
    NAME = "display_panel"

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[Tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size, "")

        self.come_from = ""
        self.i_cache_key = ''
        self.i_cache = {}

    def fresh(self):
        pass

    def update(self, action, **data):
        if action == "goto":
            self.i_cache[self.i_cache_key] = self._i

            self.come_from = data.get("source", "")
            self.i_cache_key = data.get('key', '')
            self._content = data.get("content", "")

            self._i = self.i_cache.get(self.i_cache_key, 0)
            self._render()

    def on_key(self, key: str):
        if key in {"esc", "q"}:
            self.emit("goto", target=self.come_from)
        elif key == "j":
            self.scroll_down()
        elif key == "k":
            self.scroll_up()
        elif key == "J":
            self.scroll_down(5)
        elif key == "K":
            self.scroll_up(5)


class PanelContainer(Container):
    NAME = "container"

    def __init__(self) -> None:
        status_panel = StatusPanel()
        branch_panel = BranchPanel()
        commit_panel = CommitPanel()
        display_panel = ContentDisplay()

        children = {
            status_panel.NAME: status_panel,
            branch_panel.NAME: branch_panel,
            commit_panel.NAME: commit_panel,
            display_panel.NAME: display_panel,
        }
        # print(children)

        def get_name(key: str):
            return {
                "1": status_panel.NAME,
                "2": branch_panel.NAME,
                "3": commit_panel.NAME,
            }.get(key, "")

        super().__init__(children, start_name=status_panel.NAME, switch_handle=get_name)


class App(EventLoop):
    BINDINGS = [
        ("Q", "quit"),
    ]

    def __init__(self) -> None:
        super().__init__(PanelContainer())

        self.set_input_timeouts(0.125)
