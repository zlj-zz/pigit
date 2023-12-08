import os
import stat
import shutil
import pytest
from unittest.mock import patch

from .conftest import TEST_PATH

from pigit.ext.executor import WAITING, Executor
from pigit.git import git_version
from pigit.git.repo import Repo


exec_patch = "pigit.git._cmd_func.Executor.exec"


def create_repo(test_repo: str):
    executor = Executor()

    # re-create test repo
    if os.path.isdir(test_repo):
        shutil.rmtree(
            test_repo,
            onerror=lambda func, path, _: (
                # Fix `PermissionError` on windows.
                # Will deprecated `onerror` on Py312.
                os.chmod(path, stat.S_IWRITE),
                func(path),
            ),
        )
    os.makedirs(test_repo, exist_ok=True)
    print(executor.exec("git init", flags=WAITING, cwd=test_repo))
    print(executor.exec("git config user.name Zachary", flags=WAITING, cwd=test_repo))
    print(
        executor.exec(
            "git config user.email zlj19971222@outlook.com",
            flags=WAITING,
            cwd=test_repo,
        )
    )
    print(executor.exec("git branch -m A", flags=WAITING, cwd=test_repo))
    print(
        executor.exec(
            "git remote add origin https://github.com/zlj-zz/test-repo.git",
            flags=WAITING,
            cwd=test_repo,
        )
    )

    # create no.1 file and first commit
    with open(os.path.join(test_repo, "test1.txt"), "w") as f:
        f.write("""This is a test file.""")
    print(executor.exec("git add .", flags=WAITING, cwd=test_repo))
    print(executor.exec("git commit -m 'init'", flags=WAITING, cwd=test_repo))

    # create new branch
    for name in ["B", "C", "D"]:
        print(executor.exec(f"git checkout -b {name}", flags=WAITING, cwd=test_repo))
    print(executor.exec("git checkout A", flags=WAITING, cwd=test_repo))

    # create no.2 file
    with open(os.path.join(test_repo, "test2.py"), "w") as f:
        f.write("""print('This is test py file.')""")


class TestRepo:
    @classmethod
    def setup_class(cls):
        if not git_version():
            exit(1)

        # create test repo
        cls.test_repo = test_repo = os.path.join(TEST_PATH, "test_repo")
        create_repo(test_repo)

        # create git handle
        cls.git = Repo()
        cls.git.update_setting(
            op_path=test_repo, repo_info_path=os.path.join(test_repo, "repos.json")
        )

    def test(self):
        git = self.git

        assert git.get_head() == "A"

        assert git.get_branches() == ["A", "B", "C", "D"]
        assert git.get_branches("xxxx") == []

        # has no upstream
        assert git.get_first_pushed_commit() == ""
        assert git.get_first_pushed_commit("xxxx") == ""

        assert git.get_remotes() == ["origin"]

        assert git.get_remote_url() == "https://github.com/zlj-zz/test-repo"

        print()
        print(git.get_repo_desc())
        print(git.get_config())

    def test_api(self):
        git = self.git
        print(git.load_branches())
        print(git.load_log())
        print(git.load_status())
        print(git.load_file_diff("example.py", tracked=False))
        print(git.load_commits("A"))
        print(git.load_commit_info())

    @pytest.mark.parametrize(
        ["get_path", "expected"],
        [
            [(-1, "err", ""), ("", "")],
            [(0, "", "a/b/.git"), ("a/b", "a/b/.git")],
            [(0, "", "a/b/.git/modules/"), ("a/b/", "a/b/.git/modules/")],
        ],
    )
    @patch(exec_patch)
    def test_get_repo_info(self, mock_exec_cmd, get_path, expected):
        mock_exec_cmd.return_value = get_path
        assert self.git.confirm_repo() == expected

    def test_get_repo_info_2(self):
        git = self.git
        test_repo = self.test_repo
        assert git.confirm_repo() == (test_repo, os.path.join(test_repo, ".git"))
        assert git.confirm_repo("xxxxxxx") == ("", "")
