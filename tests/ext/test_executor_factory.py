# -*- coding:utf-8 -*-

import pytest

from pigit.ext.executor import REPLY, WAITING
from pigit.ext.executor_factory import (
    LocalExecutor,
    MockExecutor,
    get_executor,
    reset_executor,
    set_executor,
)
from pigit.git.api import GitApi


@pytest.fixture(autouse=True)
def _reset_executor_factory():
    reset_executor()
    yield
    reset_executor()


def test_get_returns_local_executor():
    ex = get_executor()
    assert isinstance(ex, LocalExecutor)


def test_get_reuses_singleton():
    assert get_executor() is get_executor()


def test_reset_builds_fresh_singleton():
    a = get_executor()
    reset_executor()
    b = get_executor()
    assert a is not b


def test_set_strategy_mock():
    mock = MockExecutor()
    set_executor(mock)
    assert get_executor() is mock


def test_mock_exec_records_and_responds():
    mock = MockExecutor(
        responses={"git status": (0, "", " M foo\n")},
        default=(1, "e", ""),
    )
    set_executor(mock)
    assert get_executor().exec("git status", flags=REPLY) == (0, "", " M foo\n")
    assert get_executor().exec("other", flags=REPLY) == (1, "e", "")
    assert len(mock.exec_calls) == 2
    assert mock.exec_calls[0][0] == "git status"


def test_mock_exec_stream_splits_buffered_stdout():
    ex = MockExecutor(
        responses={
            "git log": (
                0,
                "",
                "a|1|x||||m1\nb|2|y||||m2",
            )
        }
    )
    assert list(ex.exec_stream("git log", cwd="/r")) == [
        "a|1|x||||m1",
        "b|2|y||||m2",
    ]


def test_mock_exec_stream_empty_on_stderr():
    ex = MockExecutor(responses={"bad": (0, "e", "out")})
    assert list(ex.exec_stream("bad")) == []


def test_mock_exec_parallel_merges_orders():
    mock = MockExecutor(responses={"a": (0, "", "A"), "b": (0, "", "B")})
    set_executor(mock)
    out = mock.exec_parallel("a", "b", orders=[{"cwd": "/x"}, {}], flags=WAITING)
    assert out == [(0, "", "A"), (0, "", "B")]
    assert mock.exec_calls[0][2].get("cwd") == "/x"


def test_repo_uses_factory_executor(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    root_s = str(root.resolve())
    mock = MockExecutor(
        responses={
            "git rev-parse --show-toplevel": (0, "", root_s + "\n"),
            "git rev-parse --git-dir": (0, "", ".git\n"),
        }
    )
    set_executor(mock)
    repo = GitApi(path=root_s)
    out_root, gd = repo.confirm_repo(root_s)
    assert out_root == root_s
    assert gd.endswith(".git")
