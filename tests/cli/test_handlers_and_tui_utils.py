# -*- coding: utf-8 -*-
"""Tests for CLI handlers and small TUI helpers."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from pigit.ext.executor_factory import MockExecutor
from pigit.git.managed_repos import ManagedRepos
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
    git_api = MagicMock()
    git_api.get_remote_url.return_value = "https://github.com/user/repo"
    return SimpleNamespace(
        managed_repos=managed_repos, git_api=git_api, config=MagicMock()
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
    # `clear` asks first (it is the only handler that wipes the registry), so
    # this dispatch test answers the prompt rather than asserting it is absent.
    with (
        patch("pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)),
        patch("pigit.handlers.repo_handler.confirm", return_value=True),
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
    from pigit.git.managed_repos import Blocker, BLOCKER_FATAL

    mock_ctx.managed_repos.branch_new_repos.return_value = (
        False,
        [
            Blocker(
                name="repo-a",
                reason="branch 'feat/x' already exists",
                kind=BLOCKER_FATAL,
            )
        ],
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
    from pigit.git.managed_repos import Blocker, BLOCKER_FATAL

    mock_ctx.managed_repos.switch_repos.return_value = (
        False,
        [
            Blocker(
                name="repo-a", reason="branch 'dev' does not exist", kind=BLOCKER_FATAL
            )
        ],
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


def test_tui_handler_preprocess_unsupported_platform():
    echo = MagicMock()
    with patch(
        "pigit.handlers.base_handler.get_console", return_value=MagicMock(echo=echo)
    ):
        with patch("pigit.handlers.tui_handler.platform_supported", return_value=False):
            h = TuiHandler(MagicMock())
            assert h.preprocess() is False
    echo.assert_called_once()


def test_tui_handler_execute_first_run_skipped():
    with patch("pigit.handlers.tui_handler.IS_FIRST_RUN", True):
        with patch("pigit.handlers.tui_handler.introduce"):
            with patch("pigit.handlers.tui_handler.confirm", return_value=False):
                h = TuiHandler(MagicMock())
                with patch("pigit.app.PigitApplication") as m_app:
                    h.execute()
                m_app.assert_not_called()


def test_tui_handler_execute_runs_app():
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
    mock_ctx.git_api.get_remote_url.assert_called_once()
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
    mock_ctx.git_api.get_remote_url.assert_called_once()
    mock_wb.assert_called_once_with("https://github.com/user/repo")


def test_open_handler_no_remote(mock_ctx):
    mock_ctx.git_api.get_remote_url.return_value = ""
    echo = MagicMock()
    with patch(
        "pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)
    ):
        h = OpenHandler(mock_ctx)
        h.open_browser(SimpleNamespace(branch="", issue="", commit="", print=False))
    echo.assert_called_once()
    assert "No remote URL" in echo.call_args[0][0]


def test_tui_utils_get_width_and_plain():
    from pigit.termui.primitives.text import plain
    from pigit.termui.wcwidth_table import get_width

    assert get_width(0xE) == 0
    assert get_width(0xF) == 0
    assert get_width(999999) == 1
    assert plain("\033[1;32mhi\033[0m") == "hi"


# ── bulk_cmd reports failures to the caller ──


def _bulk_handler(results):
    from pigit.handlers.repo_handler import RepoCommandHandler

    ctx = MagicMock()
    ctx.managed_repos.process_repos_option.return_value = results
    handler = RepoCommandHandler.__new__(RepoCommandHandler)
    handler.ctx = ctx
    handler.console = MagicMock()
    handler._pick_repos = lambda *_a, **_k: ["a", "b"]
    return handler


def test_bulk_cmd_reports_the_failure_count():
    """The console summary is no use to a script; the return value is."""
    handler = _bulk_handler([("a", 0, "", ""), ("b", 1, "boom", "")])

    assert (
        handler.bulk_cmd(
            SimpleNamespace(
                repos=[],
            ),
            "git pull",
        )
        == 1
    )


def test_bulk_cmd_reports_zero_when_everything_succeeded():
    handler = _bulk_handler([("a", 0, "", ""), ("b", 0, "", "")])

    assert handler.bulk_cmd(SimpleNamespace(repos=[]), "git pull") == 0


def test_bulk_cmd_treats_a_cancelled_pick_as_not_a_failure():
    """Nothing ran, which is not the same as something failing."""
    handler = _bulk_handler([("a", 0, "", "")])
    handler._pick_repos = lambda *_a, **_k: None

    assert handler.bulk_cmd(SimpleNamespace(repos=[]), "git pull") == 0


def test_bulk_cmd_with_nothing_to_process_is_not_a_failure():
    handler = _bulk_handler([])

    assert handler.bulk_cmd(SimpleNamespace(repos=[]), "git pull") == 0


def test_a_failed_bulk_run_exits_non_zero():
    """The exit code is what a CI step reads; it used to be 0 either way."""
    from pigit.entry import _bulk_cmd_handler

    handler = _bulk_handler([("a", 0, "", ""), ("b", 1, "boom", "")])
    with patch("pigit.entry._repo_handler", return_value=handler):
        with pytest.raises(SystemExit) as exc:
            _bulk_cmd_handler("git pull")(SimpleNamespace(repos=[]), None)

    assert exc.value.code == 1


def test_a_clean_bulk_run_exits_zero():
    from pigit.entry import _bulk_cmd_handler

    handler = _bulk_handler([("a", 0, "", "")])
    with patch("pigit.entry._repo_handler", return_value=handler):
        _bulk_cmd_handler("git pull")(SimpleNamespace(repos=[]), None)  # no raise


def test_a_picker_that_cannot_run_is_a_failure_not_a_silent_success():
    """With no terminal (CI, a pipe) and no explicit names, the picker exits
    non-zero — and used to leave no output and exit 0, which is a false
    success in exactly the environment scripts run in."""
    from unittest.mock import patch as _patch

    ctx = MagicMock()
    ctx.managed_repos.load_repos.return_value = {"a": {"path": "/a"}}
    handler = RepoCommandHandler.__new__(RepoCommandHandler)
    handler.ctx = ctx
    handler.console = MagicMock()

    with _patch(
        "pigit.handlers.repo_picker.run_multi_select_picker", return_value=(1, [])
    ):
        with pytest.raises(SystemExit) as exc:
            handler.bulk_cmd(SimpleNamespace(repos=[]), "git pull")

    assert exc.value.code == 1
    assert handler.console.echo.called  # and it says why


def test_a_picker_platform_error_keeps_its_own_message():
    from unittest.mock import patch as _patch

    ctx = MagicMock()
    ctx.managed_repos.load_repos.return_value = {"a": {"path": "/a"}}
    handler = RepoCommandHandler.__new__(RepoCommandHandler)
    handler.ctx = ctx
    handler.console = MagicMock()

    with _patch(
        "pigit.handlers.repo_picker.run_multi_select_picker",
        return_value=(1, "NO PICKER ON THIS PLATFORM"),
    ):
        with pytest.raises(SystemExit):
            handler.bulk_cmd(SimpleNamespace(repos=[]), "git pull")

    assert handler.console.echo.call_args[0][0] == "NO PICKER ON THIS PLATFORM"


# ── Clearing the registry asks first ──
#
# `clear` lives on the handler but reaches the registry, so it is tested
# here with the other handlers rather than beside the registry's own tests.


@pytest.fixture
def tmp_repos_json(tmp_path):
    return tmp_path / "repos.json"


def _clear_handler(tmp_repos_json):
    ctx = Mock()
    ctx.managed_repos = ManagedRepos(MockExecutor(), repo_json_path=str(tmp_repos_json))
    handler = RepoCommandHandler.__new__(RepoCommandHandler)
    handler.ctx = ctx
    handler.console = Mock()
    return handler, ctx.managed_repos


def test_clear_keeps_everything_when_declined(tmp_repos_json):
    """`clear` used to unlink the file with no question at all."""
    tmp_repos_json.write_text(json.dumps({"a": {"path": "/a"}}))
    handler, _mr = _clear_handler(tmp_repos_json)

    with patch("pigit.handlers.repo_handler.confirm", return_value=False):
        handler.clear()

    assert tmp_repos_json.exists()


def test_clear_deletes_once_confirmed(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"a": {"path": "/a"}}))
    handler, _mr = _clear_handler(tmp_repos_json)

    with patch("pigit.handlers.repo_handler.confirm", return_value=True):
        handler.clear()

    assert not tmp_repos_json.exists()


def test_clear_asks_with_the_count(tmp_repos_json):
    tmp_repos_json.write_text(json.dumps({"a": {"path": "/a"}, "b": {"path": "/b"}}))
    handler, _mr = _clear_handler(tmp_repos_json)

    with patch("pigit.handlers.repo_handler.confirm", return_value=False) as asked:
        handler.clear()

    assert "2" in asked.call_args[0][0]


def test_clear_on_an_empty_registry_does_not_ask(tmp_repos_json):
    handler, _mr = _clear_handler(tmp_repos_json)

    with patch("pigit.handlers.repo_handler.confirm") as asked:
        handler.clear()

    asked.assert_not_called()
