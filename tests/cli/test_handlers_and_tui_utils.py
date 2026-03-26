# -*- coding: utf-8 -*-
"""Tests for CLI handlers and small TUI helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pigit.handlers.cmd_handler import CmdHandler
from pigit.handlers.repo_commands import RepoCommandHandler
from pigit.handlers.tui_handler import TuiHandler


@pytest.fixture
def mock_ctx():
    repo = MagicMock()
    repo.cd_repo.return_value = (0, None)
    repo.add_repos.return_value = ["/a", "/b"]
    repo.rm_repos.return_value = [("n", "/p")]
    repo.rename_repo.return_value = (True, "ok")
    repo.ll_repos.return_value = iter(
        [
            [
                ("repo1", ""),
                ("Branch", "main"),
                ("Status", "s"),
                ("Commit Hash", "h"),
                ("Commit Msg", "m"),
                ("Local Path", "/lp"),
            ]
        ]
    )
    repo.report_repos.return_value = "report-text"
    repo.open_repo_in_browser.return_value = (0, "opened")
    return SimpleNamespace(repo=repo, config=MagicMock())


def test_repo_handler_add_found(mock_ctx):
    echo = MagicMock()
    with patch("plenty.get_console", return_value=MagicMock(echo=echo)):
        h = RepoCommandHandler(mock_ctx)
        args = SimpleNamespace(paths=["/x"], dry_run=False)
        h.add(args)
    mock_ctx.repo.add_repos.assert_called_once()
    assert echo.call_count >= 2


def test_repo_handler_add_none(mock_ctx):
    mock_ctx.repo.add_repos.return_value = []
    echo = MagicMock()
    with patch("plenty.get_console", return_value=MagicMock(echo=echo)):
        h = RepoCommandHandler(mock_ctx)
        h.add(SimpleNamespace(paths=[], dry_run=False))
    echo.assert_called()


def test_repo_handler_rm_rename_report_cd_process_open(mock_ctx):
    echo = MagicMock()
    with patch("plenty.get_console", return_value=MagicMock(echo=echo)):
        h = RepoCommandHandler(mock_ctx)
        h.rm(SimpleNamespace(repos=["n"], path=False))
        h.rename(SimpleNamespace(repo="a", new_name="b"))
        h.ll(SimpleNamespace(simple=True, reverse=False))
        h.ll(SimpleNamespace(simple=True, reverse=True))
        h.ll(SimpleNamespace(simple=False, reverse=True))
        h.ll(SimpleNamespace(simple=False, reverse=False))
        h.clear()
        h.report(SimpleNamespace(author="x", since="", until=""))
        h.cd(SimpleNamespace(repo="r"))
        h.process_repos_option(["a"], "git pull")
        h.open_browser(
            SimpleNamespace(
                branch=None, issue=None, commit=None, print=False
            )
        )
    mock_ctx.repo.clear_repos.assert_called_once()
    mock_ctx.repo.report_repos.assert_called_once()
    mock_ctx.repo.cd_repo.assert_called_once_with("r", pick=False, pick_alt_screen=False)
    mock_ctx.repo.process_repos_option.assert_called_once()
    mock_ctx.repo.open_repo_in_browser.assert_called_once()


def test_tui_handler_preprocess_windows():
    with patch("pigit.handlers.tui_handler.IS_WIN", True):
        h = TuiHandler(MagicMock())
        assert h.preprocess() is False


def test_tui_handler_execute_first_run_skipped():
    with patch("pigit.handlers.tui_handler.IS_WIN", False):
        with patch("pigit.handlers.tui_handler.IS_FIRST_RUN", True):
            with patch("pigit.handlers.tui_handler.introduce"):
                with patch("pigit.handlers.tui_handler.confirm", return_value=False):
                    h = TuiHandler(MagicMock())
                    with patch("pigit.app.App") as m_app:
                        h.execute()
                    m_app.assert_not_called()


def test_tui_handler_execute_runs_app():
    with patch("pigit.handlers.tui_handler.IS_WIN", False):
        with patch("pigit.handlers.tui_handler.IS_FIRST_RUN", False):
            h = TuiHandler(MagicMock())
            with patch("pigit.app.App") as m_app:
                h.execute()
            m_app.return_value.run.assert_called_once()


@pytest.fixture
def cmd_ctx(mock_ctx):
    mock_ctx.config.repo_auto_append = False
    mock_ctx.config.cmd_recommend = False
    mock_ctx.config.cmd_display = False
    return mock_ctx


def test_cmd_handler_mutex_list_and_search(cmd_ctx):
    echo = MagicMock()
    args = SimpleNamespace(
        shell=False,
        cmd_list=True,
        cmd_search=["x"],
        cmd_pick=False,
        cmd_type=None,
        command=None,
        args=[],
    )
    with patch(
        "pigit.handlers.base_handler.get_console", return_value=MagicMock(echo=echo)
    ):
        with patch("pigit.handlers.cmd_handler.get_extra_cmds", return_value={}):
            with pytest.raises(SystemExit) as exc:
                CmdHandler(cmd_ctx, args, []).execute()
    assert exc.value.code == 2


def test_cmd_handler_search_no_match(cmd_ctx):
    echo = MagicMock()
    args = SimpleNamespace(
        shell=False,
        cmd_list=False,
        cmd_search=["zzznoexisttoken999"],
        cmd_pick=False,
        cmd_type=None,
        command=None,
        args=[],
    )
    with patch(
        "pigit.handlers.base_handler.get_console", return_value=MagicMock(echo=echo)
    ):
        with patch("pigit.handlers.cmd_handler.get_extra_cmds", return_value={}):
            with pytest.raises(SystemExit) as exc:
                CmdHandler(cmd_ctx, args, []).execute()
    assert exc.value.code == 1


def test_repo_handler_cd_pick_no_tty(mock_ctx):
    echo = MagicMock()
    mock_ctx.repo.cd_repo.return_value = (1, "needs tty")
    args = SimpleNamespace(repo=None, repo_cd_pick=True)
    with patch("plenty.get_console", return_value=MagicMock(echo=echo)):
        with pytest.raises(SystemExit) as exc:
            RepoCommandHandler(mock_ctx).cd(args)
    assert exc.value.code == 1
    echo.assert_called_once_with("needs tty")


def test_cmd_handler_pick_no_tty(cmd_ctx):
    echo = MagicMock()
    args = SimpleNamespace(
        shell=False,
        cmd_list=False,
        cmd_search=None,
        cmd_pick=True,
        cmd_type=None,
        command=None,
        args=[],
    )
    with patch(
        "pigit.handlers.base_handler.get_console", return_value=MagicMock(echo=echo)
    ):
        with patch("pigit.handlers.cmd_handler.get_extra_cmds", return_value={}):
            with patch("pigit.git.cmd_picker._tty_ok", return_value=False):
                with pytest.raises(SystemExit) as exc:
                    CmdHandler(cmd_ctx, args, []).execute()
    assert exc.value.code == 1
    echo.assert_called()


def test_cmd_handler_type_list_sentinel(cmd_ctx):
    echo = MagicMock()
    from pigit.const import CMD_TYPE_LIST_SENTINEL

    args = SimpleNamespace(
        shell=False,
        cmd_list=False,
        cmd_search=None,
        cmd_pick=False,
        cmd_type=CMD_TYPE_LIST_SENTINEL,
        command=None,
        args=[],
    )
    with patch(
        "pigit.handlers.base_handler.get_console", return_value=MagicMock(echo=echo)
    ):
        with patch("pigit.handlers.cmd_handler.get_extra_cmds", return_value={}):
            CmdHandler(cmd_ctx, args, []).execute()
    echo.assert_called()


def test_tui_utils_get_width_and_plain():
    from pigit.tui.utils import get_width, plain

    assert get_width(0xE) == 0
    assert get_width(0xF) == 0
    assert get_width(999999) == 1
    assert plain("\033[1;32mhi\033[0m") == "hi"
