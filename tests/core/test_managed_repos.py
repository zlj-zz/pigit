# -*- coding: utf-8 -*-
"""Unit tests for :mod:`pigit.git.managed_repos`."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from pigit.ext.executor_factory import MockExecutor
from pigit.git.local_git import LocalGit
from pigit.git.managed_repos import ManagedRepos
from pigit.git.repo import Repo


@pytest.fixture
def tmp_repos_json(tmp_path):
    return tmp_path / "repos.json"


def _rev_parse_responses(repo_root: str) -> dict:
    top = str(repo_root)
    return {
        "git rev-parse --show-toplevel": (0, "", top + "\n"),
        "git rev-parse --git-dir": (0, "", ".git\n"),
    }


def test_repo_parallel_workers_default(monkeypatch):
    monkeypatch.delenv("PIGIT_REPO_MAX_WORKERS", raising=False)
    assert ManagedRepos._repo_parallel_workers() == 4


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("8", 8),
        ("1", 1),
        ("32", 32),
        ("99", 32),
        ("0", 1),
        ("abc", 4),
        ("", 4),
    ],
)
def test_repo_parallel_workers_env(monkeypatch, raw, expected):
    monkeypatch.setenv("PIGIT_REPO_MAX_WORKERS", raw)
    assert ManagedRepos._repo_parallel_workers() == expected


def test_make_repo_name_basename():
    repos = {}
    counts = __import__("collections").Counter()
    assert ManagedRepos._make_repo_name("/a/myrepo", repos, counts) == "myrepo"


def test_make_repo_name_collision_with_existing():
    repos = {"myrepo": {"path": "/x"}}
    counts = __import__("collections").Counter()
    assert ManagedRepos._make_repo_name("/a/myrepo", repos, counts) == os.path.join(
        "a", "myrepo"
    )


def test_make_repo_name_duplicate_batch():
    repos = {}
    from collections import Counter

    counts = Counter(["proj", "proj"])
    assert ManagedRepos._make_repo_name("/parent/proj", repos, counts) == os.path.join(
        "parent", "proj"
    )


def test_load_repos_missing_file(tmp_repos_json):
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    assert mr.load_repos() == {}


def test_load_repos_reads_json(tmp_repos_json):
    data = {"n": {"path": "/p"}}
    tmp_repos_json.write_text(json.dumps(data))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    assert mr.load_repos() == data


def test_dump_repos_success(tmp_repos_json):
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    assert mr.dump_repos({"a": {"path": "/x"}}) is True
    assert json.loads(tmp_repos_json.read_text()) == {"a": {"path": "/x"}}


def test_dump_repos_failure_logs(tmp_repos_json):
    ex = MockExecutor()
    log = MagicMock()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json), log=log)
    with patch("pathlib.Path.open", side_effect=OSError("nope")):
        assert mr.dump_repos({}) is False
    log.error.assert_called()


def test_clear_repos(tmp_repos_json):
    tmp_repos_json.write_text("{}")
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    mr.clear_repos()
    assert not tmp_repos_json.is_file()


def test_report_repos_empty(tmp_repos_json):
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    msg = mr.report_repos(author="a", since="", until="")
    assert "No repo(s) managed" in msg


def test_report_repos_with_parallel(tmp_repos_json):
    tmp_repos_json.write_text(
        json.dumps({"r1": {"path": "/p1"}, "r2": {"path": "/p2"}})
    )
    ex = MockExecutor(
        responses={
            "git log --color=never --oneline -30": (
                0,
                "",
                "abc111 first line\nMerge branch x\n",
            ),
        },
        default=(0, "", ""),
    )
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    with patch("pigit.git.managed_repos.pprint.pprint"):
        mr.report_repos(author="", since="2020-01-01", until="2020-12-31")


def test_add_repos_dry_run(tmp_path, tmp_repos_json):
    root = tmp_path / "gr"
    root.mkdir()
    responses = _rev_parse_responses(root)
    ex = MockExecutor(responses=responses)
    r = Repo(executor=ex, repo_json_path=str(tmp_repos_json))
    added = r.add_repos([str(root)], dry_run=True)
    assert len(added) == 1
    assert not tmp_repos_json.is_file()


def test_add_repos_persists(tmp_path, tmp_repos_json):
    root = tmp_path / "gr"
    root.mkdir()
    responses = _rev_parse_responses(root)
    ex = MockExecutor(responses=responses)
    r = Repo(executor=ex, repo_json_path=str(tmp_repos_json))
    added = r.add_repos([str(root)], dry_run=False)
    assert added
    data = json.loads(tmp_repos_json.read_text())
    assert any(v["path"] == str(root) for v in data.values())


def test_rm_repos_by_name(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"a": {"path": "/p"}, "b": {"path": "/q"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    out = mr.rm_repos(["a"], use_path=False)
    assert out == [("a", "/p")]
    data = json.loads(tmp_repos_json.read_text())
    assert "a" not in data and "b" in data


def test_rm_repos_by_path(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"a": {"path": "/p"}, "b": {"path": "/q"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    out = mr.rm_repos(["/p"], use_path=True)
    assert ("a", "/p") in out


def test_rename_repo_cases(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"old": {"path": "/p"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))

    ok, msg = mr.rename_repo("old", "old")
    assert ok is False and "same name" in msg

    ok, msg = mr.rename_repo("old", "taken")
    tmp_repos_json.write_text(
        json.dumps({"old": {"path": "/p"}, "taken": {"path": "/q"}})
    )
    ok, msg = mr.rename_repo("old", "taken")
    assert ok is False and "already in use" in msg

    tmp_repos_json.write_text(json.dumps({"old": {"path": "/p"}}))
    ok, msg = mr.rename_repo("missing", "x")
    assert ok is False and "not a valid" in msg

    ok, msg = mr.rename_repo("old", "newn")
    assert ok is True
    data = json.loads(tmp_repos_json.read_text())
    assert "newn" in data and "old" not in data


def test_cd_repo_known_name(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"r": {"path": "/tmp"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    mr.cd_repo("r")
    assert ex.exec_calls


def test_cd_repo_interactive_index(tmp_repos_json, monkeypatch):
    tmp_repos_json.write_text(json.dumps({"a": {"path": "/p1"}, "b": {"path": "/p2"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    monkeypatch.setattr("builtins.input", lambda _: "0")
    mr.cd_repo(None)
    assert ex.exec_calls


def test_cd_repo_interactive_bad_index(tmp_repos_json, monkeypatch, capsys):
    tmp_repos_json.write_text(json.dumps({"a": {"path": "/p"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    monkeypatch.setattr("builtins.input", lambda _: "99")
    mr.cd_repo(None)
    assert "out of range" in capsys.readouterr().out


def test_cd_repo_interactive_non_int(tmp_repos_json, monkeypatch, capsys):
    tmp_repos_json.write_text(json.dumps({"a": {"path": "/p"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    monkeypatch.setattr("builtins.input", lambda _: "x")
    mr.cd_repo(None)
    assert "number" in capsys.readouterr().out


def test_process_repos_option_parallel(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"a": {"path": "/p1"}, "b": {"path": "/p2"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    mr.process_repos_option(None, "git status")
    assert ex.parallel_calls


def test_process_repos_option_filtered(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"a": {"path": "/p1"}, "b": {"path": "/p2"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    mr.process_repos_option(["a"], "git fetch")
    assert ex.parallel_calls


def test_ll_repos_reverse_invalid(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"bad": {"path": "/nope"}}))
    ex = MockExecutor()
    r = Repo(executor=ex, repo_json_path=str(tmp_repos_json))
    with patch.object(LocalGit, "get_head", return_value=None):
        rows = list(r.ll_repos(reverse=True))
    assert rows and rows[0][0][0] == "bad"


def test_ll_repos_normal_summary(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"g": {"path": "/rp"}}))
    ex = MockExecutor(
        responses={
            "git diff --stat": (0, "", "1\n"),
            "git diff --stat --cached": (0, "", ""),
            "git ls-files -zo --exclude-standard": (0, "", ""),
        }
    )
    r = Repo(executor=ex, repo_json_path=str(tmp_repos_json))
    with patch.object(LocalGit, "get_head", return_value="main"):
        with patch.object(LocalGit, "get_first_pushed_commit", return_value="deadbeef"):
            with patch.object(LocalGit, "load_log", return_value="hello||[main]"):
                rows = list(r.ll_repos(reverse=False))
    assert len(rows) == 1
    assert rows[0][1][0] == "Branch"
