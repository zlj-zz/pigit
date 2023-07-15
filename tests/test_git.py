import os
import shutil
import pytest
from unittest.mock import patch

from .conftest import TEST_PATH
from pigit.common.utils import exec_cmd
from pigit.git import git_version
from pigit.git.repo import Repo


def create_repo(test_repo: str):
    if os.path.isdir(test_repo):
        shutil.rmtree(test_repo)
    os.makedirs(test_repo, exist_ok=True)
    print(exec_cmd("git init -b A", cwd=test_repo))

    with open(os.path.join(test_repo, "test1.txt"), "w") as f:
        f.write("""This is a test file.""")
    print(exec_cmd("git add .", cwd=test_repo))
    print(exec_cmd("git commit -m 'init'", cwd=test_repo))

    for name in ["B", "C", "D"]:
        print(exec_cmd(f"git checkout -b {name}", cwd=test_repo))
    print(exec_cmd("git checkout A", cwd=test_repo))

    with open(os.path.join(test_repo, "test2.py"), "w") as f:
        f.write("""print('This is test py file.')""")


class TestRepo:
    if not git_version():
        exit(1)

    # =================
    # create test repo
    # =================
    test_repo = os.path.join(TEST_PATH, "test_repo")
    create_repo(test_repo)

    git = Repo()
    git.update_setting(
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

        assert git.get_remotes() == []

        assert git.get_remote_url() == ""

        print()
        print(git.get_repo_desc())

    def test1(self):
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
            [("err", ""), ("", "")],
            [("", "a/b/.git"), ("a/b", "a/b/.git")],
            [("", "a/b/.git/modules/"), ("a/b/", "a/b/.git/modules/")],
        ],
    )
    @patch("pigit.git.repo.exec_cmd")
    def test_get_repo_info(self, mock_exec_cmd, get_path, expected):
        mock_exec_cmd.return_value = get_path
        assert self.git.confirm_repo() == expected

    def test_get_repo_info_2(self):
        git = self.git
        test_repo = self.test_repo
        assert git.confirm_repo() == (test_repo, os.path.join(test_repo, ".git"))
        assert git.confirm_repo("xxxxxxx") == ("", "")
