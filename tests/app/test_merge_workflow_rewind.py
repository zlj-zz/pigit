# -*- coding: utf-8 -*-
"""
Module: tests/app/test_merge_workflow_rewind.py
Description: MergeWorkflow records a rewind point only for successful merges.
Author: Zev
Date: 2026-08-29
"""

from __future__ import annotations

from unittest.mock import Mock, call, patch

import pytest

from pigit.app_merge_workflow import MergeWorkflow
from pigit.git.api import GitError


def _workflow(*, git: Mock, record: Mock) -> MergeWorkflow:
    return MergeWorkflow(
        store=Mock(),
        network=Mock(),
        get_git=lambda: git,
        navigate_product=Mock(),
        get_branch_panel=Mock(),
        get_alert_dialog=lambda: Mock(),
        get_refresh_git_vms=Mock(),
        get_schedule_reload_header=Mock(),
        get_record_rewind=lambda: record,
    )


def test_merge_success_records_rewind_with_pre_merge_sha():
    record = Mock()
    git = Mock()
    git.resolve_head_sha.return_value = "premerge0123456789"
    workflow = _workflow(git=git, record=record)
    with (
        patch("pigit.app_merge_workflow.show_spinner"),
        patch("pigit.app_merge_workflow.hide_spinner"),
    ):
        workflow.do_merge_workflow("feat", "main")
    git.checkout_branch.assert_called_once_with("main")
    git.pull.assert_called_once()
    git.merge.assert_called_once_with("feat")
    # pre_sha is the target's pre-merge HEAD, captured before the merge ran.
    record.assert_called_once_with("Merge feat into main", "premerge0123456789")


def test_merge_conflict_does_not_record():
    record = Mock()
    git = Mock()
    git.resolve_head_sha.return_value = "premerge0123456789"
    git.merge.side_effect = GitError("Merge conflict: CONFLICT (content)")
    workflow = _workflow(git=git, record=record)
    with (
        patch("pigit.app_merge_workflow.show_spinner"),
        patch("pigit.app_merge_workflow.hide_spinner"),
        patch("pigit.app_merge_workflow.show_toast"),
    ):
        with pytest.raises(GitError):
            workflow.do_merge_workflow("feat", "main")
    record.assert_not_called()
    # Failure path best-effort checks out back to source.
    git.checkout_branch.assert_has_calls([call("main"), call("feat")])


def test_pull_failure_does_not_record():
    record = Mock()
    git = Mock()
    git.pull.side_effect = GitError("Pull failed")
    workflow = _workflow(git=git, record=record)
    with (
        patch("pigit.app_merge_workflow.show_spinner"),
        patch("pigit.app_merge_workflow.hide_spinner"),
    ):
        with pytest.raises(GitError):
            workflow.do_merge_workflow("feat", "main")
    record.assert_not_called()
    git.merge.assert_not_called()
    git.resolve_head_sha.assert_not_called()
