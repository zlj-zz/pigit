# -*- coding: utf-8 -*-
"""
Module: tests/app/test_reflog_recovery.py
Description: '; reflog' lightweight recovery — palette tuples, dispatch forms,
confirm + dirty guard, hard reset, and u-reversibility via push_rewind.
Author: Zev
Date: 2026-08-31
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from pigit.app import PigitApplication
from pigit.config_data import AppConfig
from pigit.git.model import ReflogEntry
from pigit.termui import FeedbackKind, keys


def _entries() -> list[ReflogEntry]:
    now = int(time.time())
    return [
        ReflogEntry(
            sha="a" * 40,
            refish="HEAD@{0}",
            message="commit: current work",
            when=now - 60,
        ),
        ReflogEntry(
            sha="b" * 40,
            refish="HEAD@{1}",
            message="commit: fix typo in docs",
            when=now - 3600,
        ),
        ReflogEntry(
            sha="c" * 40,
            refish="HEAD@{2}",
            message="rebase (finish): refs/heads/dev",
            when=now - 7200,
        ),
    ]


@pytest.fixture
def app():
    application = PigitApplication(config=AppConfig())
    application._git = MagicMock()
    application._git.list_reflog.return_value = _entries()
    application._git.status_porcelain.return_value = ""
    application._git.resolve_head_sha.return_value = "pre" + "9" * 37
    application._tab_view = MagicMock()
    application._tab_view.visible = None
    return application


def _auto_confirm(app, *, confirmed: bool = True) -> None:
    def fake_alert(message, on_result, kind=None):
        on_result(confirmed)
        return True

    app._alert_dialog.alert = fake_alert


# ── palette entry ──


def test_catalog_includes_reflog_parameterized_item():
    from pigit.app_command_palette import build_catalog

    catalog = build_catalog(
        None, branch_names=lambda: [], file_names=lambda: []
    )
    by_id = {i.id: i for i in catalog}
    assert "reflog" in by_id
    assert by_id["reflog"].desc == "Recover from reflog"
    assert by_id["reflog"].args is not None


def test_reflog_fetch_returns_value_display_tuples():
    from pigit.app_command_palette import build_catalog

    catalog = build_catalog(
        None,
        branch_names=lambda: [],
        file_names=lambda: [],
        reflog_entries=lambda: _entries(),
    )
    by_id = {i.id: i for i in catalog}
    values = by_id["reflog"].args.fetch("typo")
    assert len(values) == 1
    value, display = values[0]
    assert value == "b" * 40  # clean full sha for dispatch
    assert "bbbbbbb" in display
    assert "fix typo" in display
    assert "ago" in display


def test_palette_tuple_candidate_keeps_clean_id_and_display():
    from pigit.termui.widgets import PaletteArgs, PaletteItem
    from pigit.termui.widgets.command_palette import CommandPalette

    palette = CommandPalette(
        items=[
            PaletteItem(
                "reflog",
                "Recover from reflog",
                args=PaletteArgs(
                    label="<Entry>",
                    fetch=lambda rest: [("b" * 40, "bbbbbbb fix typo · 1h ago")],
                ),
            )
        ],
        list_slots=10,
    )
    palette.open()
    for ch in "reflog ":
        palette.handle_key(ch)
    assert palette._arg_mode == "reflog"
    assert len(palette._matched) == 1
    assert palette._matched[0].id == "reflog " + "b" * 40
    assert palette._matched[0].desc == "bbbbbbb fix typo · 1h ago"


def test_palette_tuple_tab_then_enter_submits_clean_value():
    from pigit.termui.widgets import PaletteArgs, PaletteItem
    from pigit.termui.widgets.command_palette import CommandPalette

    executed: list[str] = []
    palette = CommandPalette(
        items=[
            PaletteItem(
                "reflog",
                "Recover from reflog",
                args=PaletteArgs(
                    label="<Entry>",
                    fetch=lambda rest: [("b" * 40, "bbbbbbb fix typo · 1h ago")],
                ),
            )
        ],
        list_slots=10,
        on_execute=lambda value: executed.append(value),
    )
    palette.open()
    for ch in "reflog ":
        palette.handle_key(ch)
    palette.handle_key(keys.KEY_TAB)  # complete the selected tuple candidate
    palette.handle_key(keys.KEY_ENTER)
    # The submitted value is the clean id, not the pretty display string.
    assert executed == ["reflog " + "b" * 40]


# ── dispatch resolution (three forms) ──


def test_resolve_by_refish(app):
    assert app._resolve_reflog_entry("HEAD@{1}").sha == "b" * 40


def test_resolve_by_full_and_short_sha(app):
    assert app._resolve_reflog_entry("b" * 40).sha == "b" * 40
    assert app._resolve_reflog_entry("bbbbbbb").sha == "b" * 40


def test_resolve_by_message_substring_best_match(app):
    entry = app._resolve_reflog_entry("fix typo")
    assert entry is not None
    assert entry.message == "commit: fix typo in docs"


def test_resolve_no_match_returns_none(app):
    assert app._resolve_reflog_entry("no-such-thing") is None


def test_resolve_message_ambiguity_picks_shortest(app):
    # Two entries containing "merge" — the shortest message wins.
    app._git.list_reflog.return_value = [
        ReflogEntry(
            sha="c" * 40,
            refish="HEAD@{0}",
            message="merge: a deliberately long subject about the merge",
            when=100,
        ),
        ReflogEntry(
            sha="d" * 40,
            refish="HEAD@{1}",
            message="merge done",
            when=200,
        ),
    ]
    entry = app._resolve_reflog_entry("merge")
    assert entry is not None
    assert entry.sha == "d" * 40


# ── recovery confirm + execute ──


def test_recover_confirm_text_warns_commit_loss(app):
    seen = {}
    app._alert_dialog.alert = lambda message, on_result, kind=None: (
        seen.update(message=message, kind=kind) or True
    )
    app._recover_from_reflog("HEAD@{1}")
    assert "Recover to bbbbbbb" in seen["message"]
    assert "git reset --hard bbbbbbb" in seen["message"]
    assert "reflog 可找回" in seen["message"]
    assert seen["kind"] is FeedbackKind.ERROR


def test_recover_no_entry_toasts(app):
    with patch("pigit.app.show_toast") as toast:
        app._recover_from_reflog("bogus")
    assert "No reflog entry matches: bogus" in toast.call_args.args[0]
    app._git.hard_reset_head.assert_not_called()


def test_recover_cancel_leaves_head_untouched(app):
    _auto_confirm(app, confirmed=False)
    with (
        patch("pigit.app.show_badge"),
        patch.object(app, "_refresh_active_panel"),
    ):
        app._recover_from_reflog("HEAD@{1}")
    app._git.hard_reset_head.assert_not_called()
    assert app._session_history.peek(1) == []


def test_recover_confirm_resets_and_records_rewind(app):
    _auto_confirm(app, confirmed=True)
    with (
        patch("pigit.app.show_badge") as badge,
        patch.object(app, "_on_follow_head") as follow,
        patch.object(app, "_refresh_active_panel") as refresh,
    ):
        app._recover_from_reflog("HEAD@{1}")
    app._git.hard_reset_head.assert_called_once_with("b" * 40)
    follow.assert_called_once()
    refresh.assert_called_once()
    assert "Rewound" in badge.call_args.args[0]
    # The recovery itself is u-reversible (S2).
    record = app._session_history.peek(1)[0]
    assert record.description == "Recover to bbbbbbb"
    assert record.commands[0].op_type == "rewind"
    assert record.commands[0].payload == {"pre_sha": "pre" + "9" * 37}


def test_recovery_is_undoable_via_u(app):
    """After a recovery, ``u`` reverses it back to the pre-recovery HEAD."""
    _auto_confirm(app, confirmed=True)
    with (
        patch("pigit.app.show_badge"),
        patch.object(app, "_on_follow_head"),
        patch.object(app, "_refresh_active_panel"),
    ):
        app._recover_from_reflog("HEAD@{1}")
    app._git.hard_reset_head.assert_called_once_with("b" * 40)
    app._git.hard_reset_head.reset_mock()

    app._alert_dialog.alert = lambda message, on_result, kind=None: on_result(True)
    with (
        patch("pigit.app.show_badge"),
        patch.object(app, "_on_follow_head"),
        patch.object(app, "_refresh_active_panel"),
    ):
        app.reverse_last_action()
    app._git.hard_reset_head.assert_called_once_with("pre" + "9" * 37)


def test_recover_dirty_guard_rejects(app):
    app._git.status_porcelain.return_value = " M f.txt"
    _auto_confirm(app, confirmed=True)
    with (
        patch("pigit.app.show_toast") as toast,
        patch.object(app, "_refresh_active_panel"),
    ):
        app._recover_from_reflog("HEAD@{1}")
    app._git.hard_reset_head.assert_not_called()
    assert "uncommitted" in toast.call_args.args[0]
    assert app._session_history.peek(1) == []


def test_dispatch_reflog_routes_to_recovery(app):
    with patch.object(app, "_recover_from_reflog") as recover:
        app._on_palette_execute("reflog " + "b" * 40)
    recover.assert_called_once_with("b" * 40)


# ── undo hint ──


def test_undo_empty_history_hints_reflog(app):
    with patch("pigit.app.show_toast") as toast:
        app.reverse_last_action()
    assert "Nothing to reverse" in toast.call_args.args[0]
    assert "reflog" in toast.call_args.args[0]
