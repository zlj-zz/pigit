# -*- coding: utf-8 -*-
"""
Module: tests/app/test_repo_switcher.py
Description: Phase 4 Header RepoSlot + RepoSwitcherSheet + @ key wiring.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

import itertools

from unittest.mock import MagicMock, Mock, patch

from pigit.app import PigitApplication
from pigit.app_repo_switcher import (
    RepoSwitcherEntry,
    RepoSwitcherSheet,
    build_repo_switcher_entries,
    format_add_current_row,
    format_repo_switcher_row,
)
from pigit.app_theme import THEME
from pigit.config_data import AppConfig
from pigit.termui import Segment
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.surface import Surface
from pigit.termui.widgets import Header, RepoSlot
from pigit.termui.widgets.repo_slot import _PREFIX, _SUFFIX


def test_format_repo_switcher_row_uses_meta_fields():
    segs = format_repo_switcher_row(
        "pigit",
        {
            "branch": "dev",
            "dirty": True,
            "staged": True,
            "untracked": False,
            "ahead": 2,
            "behind": 1,
            "commit_msg": "feat: x",
        },
        is_current=True,
    )
    text = "".join(s.text for s in segs)
    assert text.startswith("● ")
    assert "pigit" in text
    assert "dev*+" in text
    assert "↑2" in text
    assert "↓1" in text
    assert "feat: x" in text


def test_format_add_current_row():
    text = "".join(s.text for s in format_add_current_row("/tmp/x"))
    assert "⊕ add current repo" in text
    assert "/tmp/x" in text


def test_build_entries_marks_current_and_add_row():
    repos = {
        "pigit": {"path": "/work/pigit", "meta": {"branch": "dev"}},
        "other": {"path": "/work/other", "meta": {}},
    }
    entries = build_repo_switcher_entries(
        repos, current_path="/work/pigit", cwd="/work/cwd"
    )
    assert entries[0].kind == "add_current"
    assert entries[0].path == "/work/cwd"
    current = [e for e in entries if e.name == "pigit"][0]
    assert current.is_current is True
    assert [e for e in entries if e.name == "other"][0].is_current is False


def test_repo_slot_click_invokes_on_open():
    opened: list[int] = []
    slot = RepoSlot(
        name="pigit", on_open=lambda: opened.append(1), fg=THEME.fg_header_repo
    )
    slot.resize((20, 1))
    assert slot.handle_mouse(
        MouseEvent(col=1, row=1, button=MouseButton.LEFT, kind=MouseKind.PRESS)
    )
    assert opened == [1]
    assert slot.preferred_width() == len(_PREFIX) + len("pigit") + len(_SUFFIX)


def test_header_left_child_paint_and_hit_delegate():
    opened: list[int] = []
    slot = RepoSlot(
        name="pigit", on_open=lambda: opened.append(1), fg=THEME.fg_header_repo
    )
    header = Header(
        left=[Segment(" · "), Segment("*"), Segment("dev")],
        left_child=slot,
        separator=False,
        id="header",
    )
    header.resize((48, 1))
    header.mount()
    surface = Surface(48, 1)
    header.paint(surface)
    line = surface.lines()[0]
    assert "@ pigit" in line
    assert "▾" in line
    assert "dev" in line

    hit = header._hit_test(2, 1)
    assert hit is not None
    component, local_col, local_row = hit
    assert component is slot
    component.handle_mouse(
        MouseEvent(
            col=local_col,
            row=local_row,
            button=MouseButton.LEFT,
            kind=MouseKind.PRESS,
        )
    )
    assert opened == [1]


def test_header_right_child_slot_geometry_ready():
    """right_child is positioned for future TabStrip without Header changes."""

    class _Stub(RepoSlot):
        def preferred_width(self, max_width: int = 999) -> int:
            return min(8, max_width)

    right = _Stub(name="tabs", on_open=None)
    header = Header(right_child=right, separator=False)
    header.resize((40, 1))
    assert right.y == 40 - 8 + 1
    assert right._size == (8, 1)


def test_switcher_sheet_filter_and_confirm():
    switched: list[str] = []
    entries = [
        RepoSwitcherEntry(
            kind="repo",
            name="alpha",
            path="/a",
            meta={"branch": "main"},
            is_current=False,
        ),
        RepoSwitcherEntry(
            kind="repo",
            name="beta",
            path="/b",
            meta={"branch": "dev"},
            is_current=True,
        ),
    ]
    sheet = RepoSwitcherSheet(entries=entries, on_switch=lambda p: switched.append(p))
    sheet.mount()
    assert len(sheet.content) == 2
    sheet.set_filter("bet")
    assert len(sheet.content) == 1
    sheet.curr_no = 0
    with patch("pigit.app_repo_switcher.dismiss_sheet"):
        sheet.confirm()
    assert switched == ["/b"]


def test_open_repo_switcher_none_managed_toasts():
    with patch("pigit.repo_session.RepoSession.build") as build:
        session = MagicMock()
        session.git = Mock()
        session.git.get_git_dir = Mock(return_value="/tmp/.git")
        session.repo_path = "/tmp"
        session.repo_name = "tmp"
        session.status_vm = MagicMock()
        session.commit_vm = MagicMock()
        session.branch_vm = MagicMock()
        for vm in (session.status_vm, session.commit_vm, session.branch_vm):
            vm.bind_repo_token = Mock()
            vm.dispose = Mock()
        build.return_value = session
        app = PigitApplication(config=AppConfig(repo_observe=False), managed_repos=None)
    with patch("pigit.app.show_toast") as toast:
        app.open_repo_switcher()
        toast.assert_called()
        assert "repos.json" in toast.call_args.args[0]


def test_open_repo_switcher_shows_sheet():
    managed = Mock()
    managed.load_repos.return_value = {
        "pigit": {"path": "/work/pigit", "meta": {"branch": "dev"}},
    }
    managed.refresh_meta.return_value = iter([])
    with patch("pigit.repo_session.RepoSession.build") as build:
        session = MagicMock()
        session.git = Mock()
        session.git.get_git_dir = Mock(return_value="/work/pigit/.git")
        session.repo_path = "/work/pigit"
        session.repo_name = "pigit"
        session.status_vm = MagicMock()
        session.commit_vm = MagicMock()
        session.branch_vm = MagicMock()
        for vm in (session.status_vm, session.commit_vm, session.branch_vm):
            vm.bind_repo_token = Mock()
            vm.dispose = Mock()
        build.return_value = session
        app = PigitApplication(
            config=AppConfig(repo_observe=False), managed_repos=managed
        )
    with patch("pigit.app.show_sheet") as show:
        app.open_repo_switcher()
        show.assert_called_once()
        args, kwargs = show.call_args
        assert kwargs.get("title_core") == " · Switch repo · "
        assert isinstance(args[0], RepoSwitcherSheet)


def test_at_key_bound_to_open_repo_switcher():
    with patch("pigit.repo_session.RepoSession.build") as build:
        session = MagicMock()
        session.git = Mock()
        session.git.get_git_dir = Mock(return_value="/tmp/.git")
        session.repo_path = "/tmp"
        session.repo_name = "tmp"
        session.status_vm = MagicMock()
        session.commit_vm = MagicMock()
        session.branch_vm = MagicMock()
        for vm in (session.status_vm, session.commit_vm, session.branch_vm):
            vm.bind_repo_token = Mock()
            vm.dispose = Mock()
        build.return_value = session
        app = PigitApplication(config=AppConfig(repo_observe=False))
    assert app._key_handlers["@"] == app.open_repo_switcher


def test_switcher_sheet_double_click_activates():
    """Two presses on the same row within the window run the switch (mouse path)."""
    switched: list[str] = []
    entries = [
        RepoSwitcherEntry(
            kind="repo",
            name="alpha",
            path="/a",
            meta={"branch": "main"},
            is_current=False,
        ),
    ]
    sheet = RepoSwitcherSheet(entries=entries, on_switch=lambda p: switched.append(p))
    sheet.resize((40, 8))
    sheet.mount()
    ev = MouseEvent(col=2, row=1, button=MouseButton.LEFT, kind=MouseKind.PRESS)
    with (
        patch("pigit.app_repo_switcher.dismiss_sheet"),
        patch(
            "pigit.termui.viewport_hit.time.monotonic",
            side_effect=itertools.count(0, 0.2),
        ),
    ):
        sheet.handle_mouse(ev)
        sheet.handle_mouse(ev)
    assert switched == ["/a"]


def test_switcher_sheet_empty_entries_show_empty_state():
    sheet = RepoSwitcherSheet(entries=[], on_switch=lambda p: None)
    sheet.mount()
    assert sheet.content == []
    assert sheet.empty_state  # the "No managed repos" copy is registered


def test_switcher_sheet_activate_add_current_row():
    added: list[str] = []
    entries = [
        RepoSwitcherEntry(
            kind="add_current",
            name="",
            path="/cwd",
            meta={},
            is_current=False,
        ),
    ]
    sheet = RepoSwitcherSheet(
        entries=entries,
        on_add_current=lambda p: added.append(p),
        on_switch=lambda p: None,
    )
    sheet.mount()
    with patch("pigit.app_repo_switcher.dismiss_sheet"):
        sheet.confirm()
    assert added == ["/cwd"]


def test_switcher_sheet_invalid_path_toasts():
    entries = [
        RepoSwitcherEntry(
            kind="repo",
            name="broken",
            path="",
            meta={},
            is_current=False,
        ),
    ]
    sheet = RepoSwitcherSheet(entries=entries, on_switch=lambda p: None)
    sheet.mount()
    with (
        patch("pigit.app_repo_switcher.dismiss_sheet"),
        patch("pigit.app_repo_switcher.show_toast") as toast,
    ):
        sheet.confirm()
    toast.assert_called()
    assert "Repo path missing" in toast.call_args.args[0]


def test_switcher_sheet_close_dismisses_and_notifies():
    dismissed: list[int] = []
    sheet = RepoSwitcherSheet(
        entries=[],
        on_switch=lambda p: None,
        on_dismiss=lambda: dismissed.append(1),
    )
    sheet.mount()
    with patch("pigit.app_repo_switcher.dismiss_sheet"):
        sheet.close()
    assert dismissed == [1]


def test_repo_slot_paint_truncates_long_name():
    slot = RepoSlot(name="a-very-long-repository-name", fg=THEME.fg_header_repo)
    slot.resize((10, 1))
    surface = Surface(10, 1)
    slot.paint(surface)
    line = surface.lines()[0]
    assert "…" in line
    assert len(line.rstrip()) <= 10


def test_open_repo_switcher_no_manual_dismiss():
    """M1 regression: opening the switcher replaces, never stacks, a sheet."""
    managed = Mock()
    managed.load_repos.return_value = {
        "pigit": {"path": "/work/pigit", "meta": {"branch": "dev"}},
    }
    managed.refresh_meta.return_value = iter([])
    with patch("pigit.repo_session.RepoSession.build") as build:
        session = MagicMock()
        session.git = Mock()
        session.git.get_git_dir = Mock(return_value="/work/pigit/.git")
        session.repo_path = "/work/pigit"
        session.repo_name = "pigit"
        session.status_vm = MagicMock()
        session.commit_vm = MagicMock()
        session.branch_vm = MagicMock()
        for vm in (session.status_vm, session.commit_vm, session.branch_vm):
            vm.bind_repo_token = Mock()
            vm.dispose = Mock()
        build.return_value = session
        app = PigitApplication(
            config=AppConfig(repo_observe=False), managed_repos=managed
        )
    with patch("pigit.app.show_sheet") as show:
        app.open_repo_switcher()
    assert show.call_count == 1


def test_add_current_and_switch_success_calls_switch():
    managed = Mock()
    managed.add_repos.return_value = ["/cwd"]
    with patch("pigit.repo_session.RepoSession.build") as build:
        session = MagicMock()
        session.git = Mock()
        session.git.get_git_dir = Mock(return_value="/tmp/.git")
        session.repo_path = "/tmp"
        session.repo_name = "tmp"
        session.status_vm = MagicMock()
        session.commit_vm = MagicMock()
        session.branch_vm = MagicMock()
        for vm in (session.status_vm, session.commit_vm, session.branch_vm):
            vm.bind_repo_token = Mock()
            vm.dispose = Mock()
        build.return_value = session
        app = PigitApplication(
            config=AppConfig(repo_observe=False), managed_repos=managed
        )
    with patch.object(app, "_switch_repo") as sw:
        app._add_current_and_switch("/cwd")
    managed.add_repos.assert_called_once_with(["/cwd"])
    sw.assert_called_once_with("/cwd")


def test_add_current_and_switch_failure_toasts():
    managed = Mock()
    managed.add_repos.return_value = []
    managed.load_repos.return_value = {}
    with patch("pigit.repo_session.RepoSession.build") as build:
        session = MagicMock()
        session.git = Mock()
        session.git.get_git_dir = Mock(return_value="/tmp/.git")
        session.repo_path = "/tmp"
        session.repo_name = "tmp"
        session.status_vm = MagicMock()
        session.commit_vm = MagicMock()
        session.branch_vm = MagicMock()
        for vm in (session.status_vm, session.commit_vm, session.branch_vm):
            vm.bind_repo_token = Mock()
            vm.dispose = Mock()
        build.return_value = session
        app = PigitApplication(
            config=AppConfig(repo_observe=False), managed_repos=managed
        )
    with (
        patch("pigit.app.show_toast") as toast,
        patch.object(app, "_switch_repo") as sw,
    ):
        app._add_current_and_switch("/nope")
    toast.assert_called()
    sw.assert_not_called()


def test_open_repo_switcher_refreshes_async_and_updates_rows():
    """Switcher opens instantly with stored meta; async refresh corrects rows."""
    managed = Mock()
    managed.load_repos.side_effect = [
        # Instant open reads the stored branch...
        {"pigit": {"path": "/work/pigit", "meta": {"branch": "dev"}}},
        # ...the background refresh then re-reads the live branch.
        {"pigit": {"path": "/work/pigit", "meta": {"branch": "main"}}},
    ]
    managed.refresh_meta.return_value = iter(["pigit"])
    with patch("pigit.repo_session.RepoSession.build") as build:
        session = MagicMock()
        session.git = Mock()
        session.git.get_git_dir = Mock(return_value="/work/pigit/.git")
        session.repo_path = "/work/pigit"
        session.repo_name = "pigit"
        session.status_vm = MagicMock()
        session.commit_vm = MagicMock()
        session.branch_vm = MagicMock()
        for vm in (session.status_vm, session.commit_vm, session.branch_vm):
            vm.bind_repo_token = Mock()
            vm.dispose = Mock()
        build.return_value = session
        app = PigitApplication(
            config=AppConfig(repo_observe=False), managed_repos=managed
        )
    with (
        patch("pigit.app.show_sheet") as show,
        patch("pigit.app.run_async") as ra,
    ):
        app.open_repo_switcher()

    # The sheet opened immediately from stored meta — no blocking refresh.
    show.assert_called_once()
    assert managed.load_repos.call_count == 1
    assert show.call_args.kwargs.get("title_core") == " · Switch repo · "

    # An async refresh was scheduled; run it and its UI callback.
    ra.assert_called_once()
    work, callback = ra.call_args[0]
    work()
    panel = show.call_args.args[0]
    callback(["pigit"])

    assert managed.load_repos.call_count == 2
    assert panel._entries[0].meta["branch"] == "main"
