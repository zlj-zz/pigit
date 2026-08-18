# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_push_pull.py
Description: Tests for push/pull short-commands, especially p.u.
Author: Zev
Date: 2026-08-18
"""

from pigit.git.cmds._security import SecureExecutor
from pigit.git.cmds.push_pull import push_upstream


def test_push_upstream_default_uses_current_branch_name(monkeypatch):
    """No-arg p.u must name the branch so Git stores origin/<branch> tracking."""
    monkeypatch.setattr(
        "pigit.git.cmds.push_pull._current_branch_name", lambda: "bug-fix"
    )
    cmd = push_upstream.handler([])
    assert cmd == "git push -u origin bug-fix"
    assert "$(" not in cmd
    assert "`" not in cmd


def test_push_upstream_detached_head_falls_back_to_head(monkeypatch):
    monkeypatch.setattr("pigit.git.cmds.push_pull._current_branch_name", lambda: "")
    cmd = push_upstream.handler([])
    assert cmd == "git push -u origin HEAD"


def test_push_upstream_with_args():
    cmd = push_upstream.handler(["origin", "bug-fix"])
    assert cmd == "git push -u origin bug-fix"


def test_push_upstream_default_passes_security_scan(monkeypatch):
    monkeypatch.setattr(
        "pigit.git.cmds.push_pull._current_branch_name", lambda: "bug-fix"
    )
    cmd = push_upstream.handler([])
    executor = SecureExecutor()
    assert executor._validate_command(cmd.split()) is True
