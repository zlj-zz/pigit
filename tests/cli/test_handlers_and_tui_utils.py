# -*- coding: utf-8 -*-
"""Tests for CLI handlers and small TUI helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pigit.handlers.open_handler import OpenHandler
from pigit.handlers.repo_handler import RepoCommandHandler
from pigit.handlers.tui_handler import TuiHandler


@pytest.fixture
def mock_ctx():
    managed_repos = MagicMock()
    managed_repos.load_repos.return_value = {"r": {"path": "/mock/path"}}
    managed_repos.add_repos.return_value = ["/a", "/b"]
    managed_repos.rm_repos.return_value = [("n", "/p")]
    managed_repos.rename_repo.return_value = (True, "ok")
    managed_repos.ll_repos.return_value = iter(
        [
            [
                ("repo1", ""),
                ("Branch", "main"),
                ("Status", "s"),
                ("Commit Hash", "h"),
                ("Commit Msg", "m"),
                ("Author", "a"),
                ("Local Path", "/lp"),
            ]
        ]
    )
    managed_repos.report_repos.return_value = "report-text"
    local_git = MagicMock()
    local_git.get_remote_url.return_value = "https://github.com/user/repo"
    return SimpleNamespace(
        managed_repos=managed_repos, local_git=local_git, config=MagicMock()
    )


def test_repo_handler_add_found(mock_ctx):
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        h = RepoCommandHandler(mock_ctx)
        args = SimpleNamespace(paths=["/x"], dry_run=False)
        h.add(args)
    mock_ctx.managed_repos.add_repos.assert_called_once()
    assert echo.call_count >= 2


def test_repo_handler_add_none(mock_ctx):
    mock_ctx.managed_repos.add_repos.return_value = []
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        h = RepoCommandHandler(mock_ctx)
        h.add(SimpleNamespace(paths=[], dry_run=False))
    echo.assert_called()


def test_repo_handler_rm_rename_report_cd_open(mock_ctx):
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
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
    mock_ctx.managed_repos.clear_repos.assert_called_once()
    mock_ctx.managed_repos.report_repos.assert_called_once()


def test_repo_handler_ll_filter(mock_ctx):
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        h = RepoCommandHandler(mock_ctx)
        h.ll(SimpleNamespace(simple=True, reverse=False, filter="web"))
    mock_ctx.managed_repos.ll_repos.assert_called_once_with(
        reverse=False, filter_query="web"
    )


def test_mkbranch_explicit_repos(mock_ctx):
    mock_ctx.managed_repos.branch_new_repos.return_value = (
        True,
        [],
        [("repo-a", 0, None)],
    )
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        h = RepoCommandHandler(mock_ctx)
        args = SimpleNamespace(
            branch_name="feat/x",
            repos=["repo-a"],
            checkout=False,
            base=None,
            force=False,
            dry_run=False,
            filter_regex="",
        )
        h.mkbranch(args)
    mock_ctx.managed_repos.branch_new_repos.assert_called_once_with(
        "feat/x", ["repo-a"], checkout=False, base=None, force=False, dry_run=False
    )
    echo.assert_called()


def test_mkbranch_interactive(mock_ctx):
    mock_ctx.managed_repos.load_repos.return_value = {"repo-a": {"path": "/p1"}}
    mock_ctx.managed_repos.branch_new_repos.return_value = (
        True,
        [],
        [("repo-a", 0, None)],
    )
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        with patch(
            "pigit.handlers.repo_picker.run_multi_select_picker",
            return_value=(0, ["repo-a"]),
        ) as mock_picker:
            h = RepoCommandHandler(mock_ctx)
            args = SimpleNamespace(
                branch_name="feat/x",
                repos=[],
                checkout=False,
                base=None,
                force=False,
                dry_run=False,
                filter_regex="repo",
            )
            h.mkbranch(args)
    mock_picker.assert_called_once()
    _, kwargs = mock_picker.call_args
    assert kwargs["initial_filter"] == "repo"
    mock_ctx.managed_repos.branch_new_repos.assert_called_once()


def test_mkbranch_blockers_exit_1(mock_ctx):
    mock_ctx.managed_repos.branch_new_repos.return_value = (
        False,
        [("repo-a", "branch 'feat/x' already exists")],
        [],
    )
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        h = RepoCommandHandler(mock_ctx)
        args = SimpleNamespace(
            branch_name="feat/x",
            repos=["repo-a"],
            checkout=False,
            base=None,
            force=False,
            dry_run=False,
            filter_regex="",
        )
        with pytest.raises(SystemExit) as exc:
            h.mkbranch(args)
    assert exc.value.code == 1


def test_mkbranch_dry_run(mock_ctx):
    mock_ctx.managed_repos.branch_new_repos.return_value = (True, [], [])
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        h = RepoCommandHandler(mock_ctx)
        args = SimpleNamespace(
            branch_name="feat/x",
            repos=["repo-a"],
            checkout=False,
            base=None,
            force=False,
            dry_run=True,
            filter_regex="",
        )
        h.mkbranch(args)
    mock_ctx.managed_repos.branch_new_repos.assert_called_once()
    # dry-run should print "Would create branch" message
    texts = [c.args[0] for c in echo.call_args_list if c.args]
    assert any("Would create" in t for t in texts)


def test_mkbranch_empty_interactive(mock_ctx):
    mock_ctx.managed_repos.load_repos.return_value = {}
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        h = RepoCommandHandler(mock_ctx)
        args = SimpleNamespace(
            branch_name="feat/x",
            repos=[],
            checkout=False,
            base=None,
            force=False,
            dry_run=False,
            filter_regex="",
        )
        h.mkbranch(args)
    echo.assert_called_once()
    mock_ctx.managed_repos.branch_new_repos.assert_not_called()


def test_switch_explicit_repos(mock_ctx):
    mock_ctx.managed_repos.switch_repos.return_value = (
        True,
        [],
        [("repo-a", 0, None)],
    )
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        h = RepoCommandHandler(mock_ctx)
        args = SimpleNamespace(
            branch_name="dev",
            repos=["repo-a"],
            create=False,
            force=False,
            dry_run=False,
            filter_regex="",
        )
        h.switch(args)
    mock_ctx.managed_repos.switch_repos.assert_called_once_with(
        "dev", ["repo-a"], create=False, force=False, dry_run=False
    )


def test_switch_blockers_exit_1(mock_ctx):
    mock_ctx.managed_repos.switch_repos.return_value = (
        False,
        [("repo-a", "branch 'dev' does not exist")],
        [],
    )
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        h = RepoCommandHandler(mock_ctx)
        args = SimpleNamespace(
            branch_name="dev",
            repos=["repo-a"],
            create=False,
            force=False,
            dry_run=False,
            filter_regex="",
        )
        with pytest.raises(SystemExit) as exc:
            h.switch(args)
    assert exc.value.code == 1


def test_switch_dry_run(mock_ctx):
    mock_ctx.managed_repos.switch_repos.return_value = (True, [], [])
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        h = RepoCommandHandler(mock_ctx)
        args = SimpleNamespace(
            branch_name="dev",
            repos=["repo-a"],
            create=False,
            force=False,
            dry_run=True,
            filter_regex="",
        )
        h.switch(args)
    mock_ctx.managed_repos.switch_repos.assert_called_once()
    texts = [c.args[0] for c in echo.call_args_list if c.args]
    assert any("Would switch" in t for t in texts)


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
                    with patch("pigit.app.PigitApplication") as m_app:
                        h.execute()
                    m_app.assert_not_called()


def test_tui_handler_execute_runs_app():
    with patch("pigit.handlers.tui_handler.IS_WIN", False):
        with patch("pigit.handlers.tui_handler.IS_FIRST_RUN", False):
            h = TuiHandler(MagicMock())
            with patch("pigit.app.PigitApplication") as m_app:
                h.execute()
            m_app.return_value.run.assert_called_once()


def test_repo_handler_cd_pick_no_tty(mock_ctx):
    echo = MagicMock()
    mock_ctx.managed_repos.load_repos.return_value = {"r": {"path": "/p"}}
    args = SimpleNamespace(repo=None, repo_cd_pick=True, repo_cd_output_file=None)
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        with patch("pigit.handlers.repo_picker.tty_ok", return_value=False):
            with pytest.raises(SystemExit) as exc:
                RepoCommandHandler(mock_ctx).cd(args)
    assert exc.value.code == 1


def test_open_handler_print(mock_ctx):
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        h = OpenHandler(mock_ctx)
        h.open_browser(SimpleNamespace(branch="dev", issue="", commit="", print=True))
    mock_ctx.local_git.get_remote_url.assert_called_once()
    texts = [c.args[0] for c in echo.call_args_list if c.args]
    assert any("https://github.com/user/repo/tree/dev" in t for t in texts)


def test_open_handler_open(mock_ctx):
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        with patch("webbrowser.open") as mock_wb:
            h = OpenHandler(mock_ctx)
            h.open_browser(SimpleNamespace(branch="", issue="", commit="", print=False))
    mock_ctx.local_git.get_remote_url.assert_called_once()
    mock_wb.assert_called_once_with("https://github.com/user/repo")


def test_open_handler_no_remote(mock_ctx):
    mock_ctx.local_git.get_remote_url.return_value = ""
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        h = OpenHandler(mock_ctx)
        h.open_browser(SimpleNamespace(branch="", issue="", commit="", print=False))
    echo.assert_called_once()
    assert "No remote URL" in echo.call_args[0][0]


def test_tui_utils_get_width_and_plain():
    from pigit.termui._text import plain
    from pigit.termui.wcwidth_table import get_width

    assert get_width(0xE) == 0
    assert get_width(0xF) == 0
    assert get_width(999999) == 1
    assert plain("\033[1;32mhi\033[0m") == "hi"
