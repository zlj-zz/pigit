"""
Module: tests/app/test_command_palette_execute.py
Description: App-level command palette execute routing.
Author: Zev
Date: 2026-08-21
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pigit.app import PigitApplication
from pigit.config_data import AppConfig
from pigit.termui import FeedbackKind


@pytest.fixture
def app():
    application = PigitApplication(config=AppConfig())
    application._git = MagicMock()
    application._root = MagicMock()
    return application


def test_unknown_command_toasts(app):
    with patch("pigit.app.show_toast") as toast:
        app._on_palette_execute("checkout")
    toast.assert_called_once()
    assert "Unknown command" in toast.call_args[0][0]
    assert toast.call_args[1]["kind"] is FeedbackKind.WARNING


def test_stash_focuses_stash_panel(app):
    with patch.object(app, "goto_stash") as goto:
        app._on_palette_execute("stash")
    goto.assert_called_once()


def test_toggle_palette_sets_slots_from_root_and_opens_sheet(app):
    from pigit.app_command_palette import CommandPalette
    from pigit.termui.widgets.command_palette import list_slots_for_term
    from pigit.termui.widgets.sheet import Sheet

    app._palette = CommandPalette(
        on_execute=app._on_palette_execute,
        on_dismiss=app._dismiss_palette,
    )
    app._git.sequencer_in_progress.return_value = None
    app._root._size = (120, 40)

    app.toggle_palette()

    expected_slots = list_slots_for_term(40)
    assert app._palette._list_slots == expected_slots
    app._root.show_sheet.assert_called_once()
    args, kwargs = app._root.show_sheet.call_args
    assert args == (app._palette,)
    assert "height" not in kwargs
    assert kwargs.get("title") == "Commands"
    assert kwargs.get("show_edge_rule", True) is True
    assert kwargs.get("bg") is None
    # Host would resolve to the same height the child reports from those slots.
    assert (
        Sheet.resolve_height(app._palette, 40) == app._palette.preferred_sheet_height()
    )


def test_catalog_hides_sequencer_when_idle():
    from pigit.app_command_palette import catalog_for_context

    ids = [i.id for i in catalog_for_context(None)]
    assert "status" in ids
    assert "continue-merge" not in ids
    assert "rebase-continue" not in ids
    assert "cherry-pick-abort" not in ids


def test_catalog_includes_rebase_when_active():
    from pigit.app_command_palette import catalog_for_context

    ids = [i.id for i in catalog_for_context("rebase")]
    assert "rebase-continue" in ids
    assert "cherry-pick-continue" not in ids
