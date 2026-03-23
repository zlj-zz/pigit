# -*- coding: utf-8 -*-
"""Tests for ``pigit repo cd --pick`` picker and ``ManagedRepos.cd_repo`` pick path."""

import json
from unittest.mock import patch

import pytest

import pigit.entry as entry_mod

from pigit.ext.executor import WAITING
from pigit.git.managed_repos import ManagedRepos
from pigit.interactive.list_picker import PickerRow
from pigit.interactive.repo_cd import (
    EMPTY_MANAGED_REPOS_MSG,
    REPO_CD_NO_TTY_MSG,
    run_repo_cd_picker,
)


class MockExecutor:
    def __init__(self) -> None:
        self.exec_calls = []

    def exec(self, cmd, **kwargs):
        self.exec_calls.append((cmd, kwargs))
        return 0, "", ""


def test_run_repo_cd_picker_empty_rows():
    ex = MockExecutor()
    code, msg = run_repo_cd_picker([], ex)
    assert code == 1
    assert msg == EMPTY_MANAGED_REPOS_MSG
    assert not ex.exec_calls


def test_run_repo_cd_picker_no_tty():
    ex = MockExecutor()
    rows = [PickerRow(title="a", detail="/p", ref="/p")]
    with patch("pigit.interactive.repo_cd.tty_ok", return_value=False):
        code, msg = run_repo_cd_picker(rows, ex)
    assert code == 1
    assert msg == REPO_CD_NO_TTY_MSG
    assert not ex.exec_calls


def test_run_repo_cd_picker_quit():
    ex = MockExecutor()
    rows = [PickerRow(title="a", detail="/p", ref="/p")]
    with patch("pigit.interactive.repo_cd.tty_ok", return_value=True):
        code, msg = run_repo_cd_picker(
            rows,
            ex,
            read_char=lambda: "q",
            write=lambda s: None,
            flush=lambda: None,
            read_line=lambda p: "",
        )
    assert (code, msg) == (0, None)
    assert not ex.exec_calls


def test_run_repo_cd_picker_confirm():
    ex = MockExecutor()
    rows = [PickerRow(title="a", detail="/p", ref="/p")]
    with patch("pigit.interactive.repo_cd.tty_ok", return_value=True):
        code, msg = run_repo_cd_picker(
            rows,
            ex,
            read_char=lambda: "\r",
            write=lambda s: None,
            flush=lambda: None,
            read_line=lambda p: "",
        )
    assert (code, msg) == (0, None)
    assert ex.exec_calls
    assert ex.exec_calls[0][1].get("flags") == WAITING


def test_cd_repo_pick_empty_repos(tmp_path):
    j = tmp_path / "r.json"
    j.write_text("{}")
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(j))
    code, msg = mr.cd_repo(None, pick=True)
    assert code == 1
    assert "managed repos" in (msg or "").lower()


def test_cd_repo_pick_exact_name_skips_tui(tmp_path):
    j = tmp_path / "r.json"
    j.write_text(json.dumps({"foo": {"path": "/tmp/x"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(j))
    with patch("pigit.git.managed_repos.run_repo_cd_picker") as m_pick:
        code, msg = mr.cd_repo("foo", pick=True)
    assert (code, msg) == (0, None)
    m_pick.assert_not_called()
    assert ex.exec_calls


def test_cd_repo_pick_prefills_filter(tmp_path):
    j = tmp_path / "r.json"
    j.write_text(json.dumps({"foo": {"path": "/tmp/x"}}))
    ex = MockExecutor()
    mr = ManagedRepos(ex, repo_json_path=str(j))
    with patch("pigit.git.managed_repos.run_repo_cd_picker") as m_pick:
        m_pick.return_value = (0, None)
        mr.cd_repo("nope", pick=True)
    m_pick.assert_called_once()
    call_kw = m_pick.call_args
    assert call_kw[1]["initial_filter"] == "nope"


@pytest.fixture(autouse=True)
def _ensure_pigit_context():
    """Re-attach context when tests import entry (see ``tests/cli/test_all_pigit.py``)."""
    entry_mod.Context.install(entry_mod.ctx)
    yield


def test_entry_repo_cd_passes_pick_flag():
    with patch.object(entry_mod.ctx.repo, "cd_repo", return_value=(0, None)) as m:
        entry_mod.pigit("repo cd --pick".split())
    m.assert_called_once_with(None, pick=True)


@pytest.mark.parametrize("stdin_tty,stdout_tty", [(True, False), (False, True)])
def test_run_repo_cd_picker_half_tty(stdin_tty, stdout_tty):
    ex = MockExecutor()
    rows = [PickerRow(title="a", detail="/p", ref="/p")]
    with patch("sys.stdin.isatty", return_value=stdin_tty):
        with patch("sys.stdout.isatty", return_value=stdout_tty):
            code, msg = run_repo_cd_picker(rows, ex)
    assert code == 1
    assert msg == REPO_CD_NO_TTY_MSG
