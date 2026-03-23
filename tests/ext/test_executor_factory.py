# -*- coding:utf-8 -*-

import pytest

from pigit.ext.executor import REPLY, WAITING
from pigit.ext.executor_factory import (
    ExecutorFactory,
    LocalExecutor,
    MockExecutor,
)
from pigit.git.repo import Repo


@pytest.fixture(autouse=True)
def _reset_executor_factory():
    ExecutorFactory.reset()
    yield
    ExecutorFactory.reset()


def test_get_returns_local_executor():
    ex = ExecutorFactory.get()
    assert isinstance(ex, LocalExecutor)


def test_get_reuses_singleton():
    assert ExecutorFactory.get() is ExecutorFactory.get()


def test_reset_builds_fresh_singleton():
    a = ExecutorFactory.get()
    ExecutorFactory.reset()
    b = ExecutorFactory.get()
    assert a is not b


def test_set_strategy_mock():
    mock = MockExecutor()
    ExecutorFactory.set_strategy(mock)
    assert ExecutorFactory.get() is mock


def test_mock_exec_records_and_responds():
    mock = MockExecutor(
        responses={"git status": (0, "", " M foo\n")},
        default=(1, "e", ""),
    )
    ExecutorFactory.set_strategy(mock)
    assert ExecutorFactory.get().exec("git status", flags=REPLY) == (0, "", " M foo\n")
    assert ExecutorFactory.get().exec("other", flags=REPLY) == (1, "e", "")
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
    ExecutorFactory.set_strategy(mock)
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
    ExecutorFactory.set_strategy(mock)
    repo = Repo(path=root_s)
    out_root, gd = repo.confirm_repo(root_s)
    assert out_root == root_s
    assert gd.endswith(".git")
