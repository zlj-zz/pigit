# -*- coding: utf-8 -*-
"""Tests for ``pigit repo cd --pick`` picker."""

from unittest.mock import patch

import pytest

from pigit.handlers.repo_picker import (
    EMPTY_MANAGED_REPOS_MSG,
    REPO_CD_NO_TTY_MSG,
    run_repo_cd_picker,
)
from pigit.picker_app import PickerRow


class MockExecutor:
    def __init__(self) -> None:
        self.exec_calls = []

    def exec(self, cmd, **kwargs):
        self.exec_calls.append((cmd, kwargs))
        return 0, "", ""


def test_run_repo_cd_picker_empty_rows():
    code, msg = run_repo_cd_picker([])
    assert code == 1
    assert msg == EMPTY_MANAGED_REPOS_MSG


def test_run_repo_cd_picker_no_tty():
    rows = [PickerRow(title="a", detail="/p", ref="/p")]
    with patch("pigit.handlers.repo_picker.tty_ok", return_value=False):
        code, msg = run_repo_cd_picker(rows)
    assert code == 1
    assert msg == REPO_CD_NO_TTY_MSG


@pytest.mark.parametrize("stdin_tty,stdout_tty", [(True, False), (False, True)])
def test_run_repo_cd_picker_half_tty(stdin_tty, stdout_tty):
    rows = [PickerRow(title="a", detail="/p", ref="/p")]
    with patch("sys.stdin.isatty", return_value=stdin_tty):
        with patch("sys.stdout.isatty", return_value=stdout_tty):
            code, msg = run_repo_cd_picker(rows)
    assert code == 1
    assert msg == REPO_CD_NO_TTY_MSG
