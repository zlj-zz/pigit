"""
Module: tests/app/test_repo_session.py
Description: RepoSession build/dispose lifecycle and app on_exit ownership tests.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.repo_session import RepoSession
from pigit.session_history import SessionHistory


def _mock_git_api():
    git_api = Mock()
    git_api.confirm_repo.return_value = ("/tmp/repo", {})
    bound = Mock()
    git_api.bind_path.return_value = bound
    return git_api, bound


def test_build_confirms_binds_and_constructs_vms():
    git_api, bound = _mock_git_api()
    session = RepoSession.build(git_api, None, SessionHistory())
    git_api.confirm_repo.assert_called_once_with(None)
    git_api.bind_path.assert_called_once_with("/tmp/repo")
    assert session.git is bound
    assert session.repo_path == "/tmp/repo"
    assert session.repo_name == "repo"
    assert session.status_vm is not None
    assert session.commit_vm is not None
    assert session.branch_vm is not None


def test_build_repo_name_uses_confirm_resolved_root():
    """Sub-directory launch: repo_name comes from the work-tree root, not cwd."""
    git_api = Mock()
    git_api.confirm_repo.return_value = ("/work/root", {})
    git_api.bind_path.return_value = Mock()
    session = RepoSession.build(git_api, None, SessionHistory())
    assert session.repo_path == "/work/root"
    assert session.repo_name == "root"


def test_dispose_idempotent():
    git_api, _bound = _mock_git_api()
    session = RepoSession.build(git_api, None, SessionHistory())
    session.dispose()
    session.dispose()  # double dispose must not raise


def test_app_on_exit_stops_observe_then_disposes_session_once():
    from pigit.app import PigitApplication
    from pigit.config_data import AppConfig

    app = PigitApplication(config=AppConfig())
    session = Mock()
    app._session = session
    observe = Mock()
    app._observe_host = observe
    app.on_exit()
    observe.stop.assert_called_once()
    session.dispose.assert_called_once()
