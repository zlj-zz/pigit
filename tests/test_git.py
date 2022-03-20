import os, sys
import pytest
from unittest.mock import patch, Mock

from .conftest import TEST_PATH
from pigit.render import get_console
from pigit.common.git import GitOption
from pigit.common.utils import exec_cmd


git = GitOption()
if not git.git_version:
    exit(0)

test_repo = os.path.join(TEST_PATH, "test_repo")
os.makedirs(test_repo, exist_ok=True)
print(exec_cmd("git init", cwd=test_repo))
with open(os.path.join(test_repo, "test1.txt"), "w") as f:
    f.write("""This is a test file.""")
print(exec_cmd("git add .", cwd=test_repo))
print(exec_cmd("git commit -m 'init'", cwd=test_repo))
with open(os.path.join(test_repo, "test2.py"), "w") as f:
    f.write("""print('This is test py file.')""")


git.update_setting(
    op_path=test_repo, repo_info_path=os.path.join(test_repo, "reps.json")
)


def test():
    print()

    print(git.get_head())
    print(git.get_branches())
    print(git.get_first_pushed_commit())
    print(git.get_remotes())
    print(git.get_remote_url())
    print(git.get_repo_desc())


def test1():
    print(git.load_branches())
    print(git.load_log())
    print(git.load_status())
    print(git.load_file_diff("example.py", tracked=False))
    print(git.load_commits("main"))
    print(git.load_commit_info(git.get_first_pushed_commit()))


@pytest.mark.parametrize(
    ["get_path", "expected"],
    [
        [("err", ""), ("", "")],
        [("", "a/b/.git"), ("a/b", "a/b/.git")],
        [("", "a/b/.git/submodule/"), ("a/b", "a/b/.git/submodule/")],
    ],
)
@patch("pigit.common.git.exec_cmd")
def test_get_repo_info(mock_exec_cmd, get_path, expected):
    mock_exec_cmd.return_value = get_path
    assert git.get_repo_info() == expected


def test_get_repo_info_2():
    assert git.get_repo_info() == (test_repo, os.path.join(test_repo, ".git"))
    assert git.get_repo_info("xxxxxxx") == ("", "")


# def pytest_sessionfinish(session, exitstatus):
#     """whole test run finishes."""
#     print("finish")
#     os.rmdir(test_repo)
