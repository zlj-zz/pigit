from time import sleep
from typing import Callable, Dict, List, Optional, Tuple

from .const import IS_WIN
from .ext.log import logger, setup_logging
from .git.repo import Repo
from .tui.components import Container, RowPanel, ItemSelector
from .tui.event_loop import EventLoop


# setup_logging(debug=True, log_file="./tui_test.log")

repo_handle = Repo()


class StatusPanel(ItemSelector):
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

        self.name = "status"
        self.repo_path, self.repo_conf = repo_handle.confirm_repo()

    def fresh(self):
        self.files = files = repo_handle.load_status(self._size[0])
        if not files:
            return ["No status changed."]

        files_str = [file.display_str for file in files]
        self.content = files_str

        self._render()

    def on_key(self, key: str):
        f = self.files[self.curr_no]

        if key == "enter":
            c = repo_handle.load_file_diff(
                f.name, f.tracked, f.has_staged_change, path=self.repo_path
            ).split("\n")
            self.emit("goto", target="display_panel", source=self.name, content=c)
        elif key in {"a", " "}:
            repo_handle.switch_file_status(f, self.repo_path)
            self.fresh()
        elif key == "i":
            repo_handle.ignore_file(f)
            self.fresh()


class BranchPanel(ItemSelector):
    CURSOR = "→"

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Tuple[int, int] | None = None,
        content: List[str] | None = None,
    ) -> None:
        super().__init__(x, y, size, content)

        self.name = "branch"
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
        self._render()

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


class CommitPanel(ItemSelector):
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

        self.name = "commit"
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
            self.emit("goto", target="display_panel", source=self.name, content=content)


class ContentDisplay(RowPanel):
    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[Tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size, "")

        self.name = "display_panel"
        self.come_from = ""

    def fresh(self):
        pass

    def update(self, action, **data):
        if action == "goto":
            self.come_from = data.get("source", "")
            self._content = data.get("content", "")
            self._index = 0
            self._render()

    def on_key(self, key: str):
        if key == "esc":
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
    def __init__(self) -> None:
        status_panel = StatusPanel()
        branch_panel = BranchPanel()
        commit_panel = CommitPanel()
        display_panel = ContentDisplay()

        children = {
            status_panel.name: status_panel,
            branch_panel.name: branch_panel,
            commit_panel.name: commit_panel,
            display_panel.name: display_panel,
        }

        def get_name(key: str):
            return {"1": "status", "2": "branch", "3": "commit"}.get(key, "")

        super().__init__(children, start_name=status_panel.name, switch_handle=get_name)


class App(EventLoop):
    BINDINGS = [
        ("Q", "quit"),
    ]

    def __init__(self) -> None:
        super().__init__(PanelContainer())

        self.set_input_timeouts(0.125)

    def run(self) -> None:
        if IS_WIN:
            print("Not support windows now.")
            return

        super().run()
