# -*- coding: utf-8 -*-
"""Unit tests for :mod:`pigit.git.managed_repos`."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from pigit.ext.executor_factory import MockExecutor
from pigit.git.api import GitApi
from pigit.git.managed_repos import ManagedRepos, _fuzzy_match, _logger


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
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    with (
        patch("pathlib.Path.open", side_effect=OSError("nope")),
        patch.object(_logger, "error") as mock_error,
    ):
        assert mr.dump_repos({}) is False
    mock_error.assert_called()


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
    r = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    added = r.add_repos([str(root)], dry_run=True)
    assert len(added) == 1
    assert not tmp_repos_json.is_file()


def test_add_repos_persists(tmp_path, tmp_repos_json):
    root = tmp_path / "gr"
    root.mkdir()
    responses = _rev_parse_responses(root)
    ex = MockExecutor(responses=responses)
    r = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
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


def test_resolve_repo_path_known_name(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"r": {"path": "/tmp"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    assert mr.resolve_repo_path("r") == "/tmp"


def test_resolve_repo_path_unknown_name(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"r": {"path": "/tmp"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    assert mr.resolve_repo_path("x") is None


def test_get_repo_names_sorted(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"b": {"path": "/p2"}, "a": {"path": "/p1"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    assert mr.get_repo_names() == ["a", "b"]


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
    r = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    with patch.object(GitApi, "get_head", return_value=None):
        rows = list(r.ll_repos(reverse=True))
    assert rows and rows[0][0][0] == "bad"


def test_ll_repos_normal_summary(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"g": {"path": "/rp"}}))
    ex = MockExecutor(
        responses={
            "git status --porcelain": (0, "", " M file.txt\n"),
        }
    )
    r = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    with patch.object(GitApi, "get_head", return_value="main"):
        with patch.object(GitApi, "get_first_pushed_commit", return_value="deadbeef"):
            with patch.object(GitApi, "load_log", return_value="hello||[main]"):
                rows = list(r.ll_repos(reverse=False))
    assert len(rows) == 1
    assert rows[0][1][0] == "Branch"


def test_fuzzy_match():
    assert _fuzzy_match("api-gateway", "apig") is True
    assert _fuzzy_match("api-gateway", "API") is True
    assert _fuzzy_match("core-api", "api") is True
    assert _fuzzy_match("frontend", "api") is False
    assert _fuzzy_match("anything", "") is True


def test_ll_repos_filter(tmp_repos_json):
    tmp_repos_json.write_text(
        json.dumps(
            {
                "alpha": {"path": "/p1"},
                "beta": {"path": "/p2"},
                "gamma": {"path": "/p3"},
            }
        )
    )
    ex = MockExecutor()
    r = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    with patch.object(GitApi, "get_head", return_value=None):
        rows = list(r.ll_repos(reverse=True, filter_query="et"))
    names = [row[0][0] for row in rows]
    assert "beta" in names
    assert "alpha" not in names
    assert "gamma" not in names


def test_ll_repos_filter_case_insensitive(tmp_repos_json):
    tmp_repos_json.write_text(
        json.dumps({"AlphaGo": {"path": "/p1"}, "beta": {"path": "/p2"}})
    )
    ex = MockExecutor()
    r = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    with patch.object(GitApi, "get_head", return_value=None):
        rows = list(r.ll_repos(reverse=True, filter_query="alp"))
    names = [row[0][0] for row in rows]
    assert "AlphaGo" in names
    assert "beta" not in names


class TestBranchNewRepos:
    def test_empty_repos(self, tmp_repos_json):
        ex = MockExecutor()
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.branch_new_repos("feat/x")
        assert ok is True
        assert blockers == []
        assert results == []

    def test_preflight_passes_and_executes(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (0, "", ".git\n"),
                "git branch --list feat/x": (0, "", ""),
                "git branch feat/x": (0, "", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.branch_new_repos("feat/x", ["repo-a"])
        assert ok is True
        assert blockers == []
        assert len(results) == 1
        assert results[0] == ("repo-a", 0, None)

    def test_preflight_blocks_existing_branch(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (0, "", ".git\n"),
                "git branch --list feat/x": (0, "", "  feat/x\n"),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.branch_new_repos("feat/x", ["repo-a"])
        assert ok is False
        assert any("already exists" in b.reason for b in blockers)
        assert results == []

    def test_preflight_blocks_unclean_workspace(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (0, "", ".git\n"),
                "git branch --list feat/x": (0, "", ""),
                "git status --porcelain": (0, "", " M file.py\n"),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.branch_new_repos("feat/x", ["repo-a"], checkout=True)
        assert ok is False
        assert any("uncommitted" in b.reason for b in blockers)
        assert results == []

    def test_dry_run(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (0, "", ".git\n"),
                "git branch --list feat/x": (0, "", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.branch_new_repos("feat/x", ["repo-a"], dry_run=True)
        assert ok is True
        assert blockers == []
        assert results == []

    def test_force_eliminates_existing_branch_blocker(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (0, "", ".git\n"),
                "git branch --list feat/x": (0, "", "  feat/x\n"),
                "git branch -f feat/x": (0, "", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.branch_new_repos("feat/x", ["repo-a"], force=True)
        assert ok is True
        assert blockers == []
        assert len(results) == 1
        assert results[0][1] == 0

    def test_preflight_blocks_invalid_repo(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (1, "not a git repo", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.branch_new_repos("feat/x", ["repo-a"])
        assert ok is False
        assert any("invalid repo" in b.reason for b in blockers)
        assert results == []

    def test_execute_failure_returns_stderr(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (0, "", ".git\n"),
                "git branch --list feat/x": (0, "", ""),
                "git branch feat/x": (1, "some error", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.branch_new_repos("feat/x", ["repo-a"])
        assert ok is True
        assert blockers == []
        assert results[0] == ("repo-a", 1, "some error")

    def test_checkout_with_base(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (0, "", ".git\n"),
                "git branch --list feat/x": (0, "", ""),
                "git status --porcelain": (0, "", ""),
                "git checkout develop && git checkout -b feat/x": (0, "", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.branch_new_repos(
            "feat/x", ["repo-a"], checkout=True, base="develop"
        )
        assert ok is True
        assert blockers == []
        assert results[0] == ("repo-a", 0, None)


class TestBranchNewReposStash:
    """Tests for :meth:`ManagedRepos.branch_new_repos_stash`."""

    def test_stash_execute_pop_success(self, tmp_repos_json):
        """Happy path: stash dirty repo, create branch, pop stash — all succeed."""
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git stash push -u -m 'pigit: auto stash before mkbranch feat/x'": (
                    0,
                    "",
                    "Saved working directory\n",
                ),
                "git branch feat/x": (0, "", ""),
                "git stash pop": (0, "", "Dropped refs/stash@{0}\n"),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        results, stash_issues = mr.branch_new_repos_stash(
            "feat/x", ["repo-a"], dirty_repos={"repo-a"}
        )
        assert len(results) == 1
        assert results[0] == ("repo-a", 0, None)
        assert stash_issues == []

    def test_stash_failure_excludes_repo(self, tmp_repos_json):
        """When stash fails, the repo is excluded from branch creation."""
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git stash push -u -m 'pigit: auto stash before mkbranch feat/x'": (
                    1,
                    "fatal: not a git repository\n",
                    "",
                ),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        results, stash_issues = mr.branch_new_repos_stash(
            "feat/x", ["repo-a"], dirty_repos={"repo-a"}
        )
        # repo excluded — no execute called, so branch command not in responses
        assert results == []
        assert any("stash failed" in desc for _, desc in stash_issues)

    def test_pop_failure_reports_issue(self, tmp_repos_json):
        """When stash pop fails, result is still success but stash issue reported."""
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git stash push -u -m 'pigit: auto stash before mkbranch feat/x'": (
                    0,
                    "",
                    "Saved working directory\n",
                ),
                "git branch feat/x": (0, "", ""),
                "git stash pop": (1, "CONFLICT: Merge conflict\n", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        results, stash_issues = mr.branch_new_repos_stash(
            "feat/x", ["repo-a"], dirty_repos={"repo-a"}
        )
        assert len(results) == 1
        assert results[0] == ("repo-a", 0, None)
        assert len(stash_issues) == 1
        assert "stash pop failed" in stash_issues[0][1]

    def test_dry_run_noop(self, tmp_repos_json):
        """dry_run=True returns immediately without executing any git commands."""
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor()
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        results, stash_issues = mr.branch_new_repos_stash(
            "feat/x", ["repo-a"], dirty_repos={"repo-a"}, dry_run=True
        )
        assert results == []
        assert stash_issues == []

    def test_no_dirty_repos_just_executes(self, tmp_repos_json):
        """When no repos are dirty, runs plain branch creation without stash/pop."""
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git branch feat/x": (0, "", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        results, stash_issues = mr.branch_new_repos_stash(
            "feat/x", ["repo-a"], dirty_repos=set()
        )
        assert len(results) == 1
        assert results[0] == ("repo-a", 0, None)
        assert stash_issues == []

    def test_checkout_with_base_and_stash(self, tmp_repos_json):
        """Stash + checkout with base branch works end-to-end."""
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git stash push -u -m 'pigit: auto stash before mkbranch feat/x'": (
                    0,
                    "",
                    "Saved working directory\n",
                ),
                "git checkout develop && git checkout -b feat/x": (0, "", ""),
                "git stash pop": (0, "", "Dropped refs/stash@{0}\n"),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        results, stash_issues = mr.branch_new_repos_stash(
            "feat/x", ["repo-a"], checkout=True, base="develop", dirty_repos={"repo-a"}
        )
        assert len(results) == 1
        assert results[0] == ("repo-a", 0, None)
        assert stash_issues == []

    def test_empty_repos_returns_empty(self, tmp_repos_json):
        """No managed repos returns empty results."""
        ex = MockExecutor()
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        results, stash_issues = mr.branch_new_repos_stash("feat/x")
        assert results == []
        assert stash_issues == []


class TestSwitchReposStash:
    """Tests for :meth:`ManagedRepos.switch_repos_stash`."""

    def test_stash_switch_pop_success(self, tmp_repos_json):
        """Happy path: stash, switch branch, pop stash."""
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git stash push -u -m 'pigit: auto stash before switch dev'": (
                    0,
                    "",
                    "Saved working directory\n",
                ),
                "git switch dev": (0, "", ""),
                "git stash pop": (0, "", "Dropped refs/stash@{0}\n"),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        results, stash_issues = mr.switch_repos_stash(
            "dev", ["repo-a"], dirty_repos={"repo-a"}
        )
        assert len(results) == 1
        assert results[0] == ("repo-a", 0, None)
        assert stash_issues == []

    def test_stash_failure_excludes_from_switch(self, tmp_repos_json):
        """Stash failure excludes the repo from switch."""
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git stash push -u -m 'pigit: auto stash before switch dev'": (
                    1,
                    "fatal: not a git repository\n",
                    "",
                ),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        results, stash_issues = mr.switch_repos_stash(
            "dev", ["repo-a"], dirty_repos={"repo-a"}
        )
        assert results == []
        assert any("stash failed" in desc for _, desc in stash_issues)

    def test_dry_run_noop(self, tmp_repos_json):
        """dry_run=True returns immediately."""
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor()
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        results, stash_issues = mr.switch_repos_stash(
            "dev", ["repo-a"], dirty_repos={"repo-a"}, dry_run=True
        )
        assert results == []
        assert stash_issues == []

    def test_force_switch_with_stash(self, tmp_repos_json):
        """Force-switch with stash works."""
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git stash push -u -m 'pigit: auto stash before switch dev'": (
                    0,
                    "",
                    "Saved working directory\n",
                ),
                "git switch -f dev": (0, "", ""),
                "git stash pop": (0, "", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        results, stash_issues = mr.switch_repos_stash(
            "dev", ["repo-a"], force=True, dirty_repos={"repo-a"}
        )
        assert len(results) == 1
        assert results[0] == ("repo-a", 0, None)
        assert stash_issues == []

    def test_create_switch_with_stash(self, tmp_repos_json):
        """Create-and-switch with stash works."""
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git stash push -u -m 'pigit: auto stash before switch feat/x'": (
                    0,
                    "",
                    "Saved working directory\n",
                ),
                "git switch -c feat/x": (0, "", ""),
                "git stash pop": (0, "", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        results, stash_issues = mr.switch_repos_stash(
            "feat/x", ["repo-a"], create=True, dirty_repos={"repo-a"}
        )
        assert len(results) == 1
        assert results[0] == ("repo-a", 0, None)
        assert stash_issues == []


class TestSwitchRepos:
    def test_switch_existing_branch(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (0, "", ".git\n"),
                "git branch --list dev": (0, "", "  dev\n"),
                "git status --porcelain": (0, "", ""),
                "git switch dev": (0, "", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.switch_repos("dev", ["repo-a"])
        assert ok is True
        assert blockers == []
        assert results[0] == ("repo-a", 0, None)

    def test_switch_branch_not_exists_no_create(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (0, "", ".git\n"),
                "git branch --list dev": (0, "", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.switch_repos("dev", ["repo-a"])
        assert ok is False
        assert any("does not exist" in b.reason for b in blockers)
        assert results == []

    def test_switch_create_missing_branch(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (0, "", ".git\n"),
                "git branch --list dev": (0, "", ""),
                "git status --porcelain": (0, "", ""),
                "git switch -c dev": (0, "", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.switch_repos("dev", ["repo-a"], create=True)
        assert ok is True
        assert blockers == []
        assert results[0] == ("repo-a", 0, None)

    def test_switch_dirty_without_force(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (0, "", ".git\n"),
                "git branch --list dev": (0, "", "  dev\n"),
                "git status --porcelain": (0, "", "M file.txt\n"),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.switch_repos("dev", ["repo-a"])
        assert ok is False
        assert any("uncommitted changes" in b.reason for b in blockers)
        assert results == []

    def test_switch_force_dirty(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (0, "", ".git\n"),
                "git branch --list dev": (0, "", "  dev\n"),
                "git switch -f dev": (0, "", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.switch_repos("dev", ["repo-a"], force=True)
        assert ok is True
        assert blockers == []
        assert results[0] == ("repo-a", 0, None)

    def test_switch_dry_run(self, tmp_repos_json):
        tmp_repos_json.write_text(json.dumps({"repo-a": {"path": "/p1"}}))
        ex = MockExecutor(
            responses={
                "git rev-parse --git-dir": (0, "", ".git\n"),
                "git branch --list dev": (0, "", "  dev\n"),
                "git status --porcelain": (0, "", ""),
            }
        )
        mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
        ok, blockers, results = mr.switch_repos("dev", ["repo-a"], dry_run=True)
        assert ok is True
        assert blockers == []
        assert results == []


def test_add_repos_confirm_false_skips_confirm_repo(tmp_repos_json):
    """before_hook passes confirm=False: already-confirmed paths are not re-probed."""
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    with patch.object(mr, "_fetch_repo_meta", return_value=None):
        added = mr.add_repos(["/already/confirmed"], confirm=False)
    assert added == ["/already/confirmed"]
    assert ex.exec_calls == []  # no confirm_repo probe, no meta probes


def test_add_repos_confirm_default_probes(tmp_path, tmp_repos_json):
    root = tmp_path / "gr"
    root.mkdir()
    ex = MockExecutor(responses=_rev_parse_responses(root))
    mr = ManagedRepos(ex, repo_json_path=str(tmp_repos_json))
    with patch.object(mr, "_fetch_repo_meta", return_value=None):
        added = mr.add_repos([str(root)])
    assert added == [str(root.resolve())]
    assert any("--show-toplevel" in str(c[0]) for c in ex.exec_calls)
