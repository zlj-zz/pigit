import pytest
from unittest.mock import patch, Mock

from pigit.render import get_console
from pigit.git_utils import (
    get_git_version,
    get_repo_info,
    get_repo_desc,
    get_head,
    get_branches,
    get_remote,
    get_first_pushed_commit,
    load_branches,
    load_log,
    load_commits,
    load_commit_info,
    load_status,
    load_file_diff,
)
from pigit.repo_utils import rename_repo


def test():
    print()

    print(get_git_version())

    print(get_branches())

    print(get_remote())


@pytest.mark.parametrize(
    ["get_path", "expected"],
    [
        [("err", ""), ("", "")],
        [("", "a/b/.git"), ("a/b", "a/b/.git")],
        [("", "a/b/.git/submodule/"), ("a/b", "a/b/.git/submodule/")],
    ],
)
@patch("pigit.git_utils.exec_cmd")
def test_get_repo_info(mock_exec_cmd, get_path, expected):
    mock_exec_cmd.return_value = get_path
    assert get_repo_info() == expected


def test_get_repo_info_2():
    assert get_repo_info("xxxxxxx") == ("", "")


def test_get_repo_desc():
    console = get_console()
    print("\n>>>>>>>>>>>>>>>show>>>>>>>>>>>>>>>>>>>>>>>")
    console.echo(get_repo_desc())
    console.echo(get_repo_desc(color=False))


def test_load():
    branches = load_branches()
    assert isinstance(branches, list)

    logs = load_log(branches[0].name, limit=10)

    status = load_status(max_width=90)

    commits = load_commits(branches[0].name)
    commit_info = load_commit_info(commits[0].sha)
