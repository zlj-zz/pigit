"""
Module: tests/app/test_observe_detail.py
Description: Refresh of the presented diffs when the Status rows change.
Author: Zev
Date: 2026-11-13
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from pigit.app import PigitApplication
from pigit.config_data import AppConfig


@pytest.fixture
def app():
    """A built app; its observe host is wired but not started."""
    application = PigitApplication(config=AppConfig())
    application.build_root()
    yield application


def test_detail_accessor_follows_the_presented_view(app):
    """The observer only sees the detail while it occupies the body."""
    deps = app._observe_host._deps

    assert deps.get_detail_panel() is None
    app._body_view.show(app._diff_panel)
    assert deps.get_detail_panel() is app._diff_panel
    app._body_view.show(app._split_pane)
    assert deps.get_detail_panel() is None


def test_fresh_rows_reload_the_presented_detail(app):
    """The reload runs on the rows that just landed, not on stale ones."""
    detail = MagicMock()
    app._observe_host._deps = replace(
        app._observe_host._deps, get_detail_panel=lambda: detail
    )

    app._observe_host._on_status_items([])

    detail.reload.assert_called_once()


def test_fresh_rows_reload_the_side_preview_when_shown(app):
    """The side preview is a view of the same rows and follows them."""
    preview = MagicMock()
    app._observe_host._deps = replace(
        app._observe_host._deps,
        get_preview_panel=lambda: preview,
        get_diff_preview_wanted=lambda: True,
        get_is_large_screen=lambda: True,
    )

    app._observe_host._on_status_items([])

    preview.reload.assert_called_once()


def test_fresh_rows_leave_the_preview_alone_when_hidden(app):
    """No preview on screen means no preview reload."""
    preview = MagicMock()
    app._observe_host._deps = replace(
        app._observe_host._deps,
        get_preview_panel=lambda: preview,
        get_diff_preview_wanted=lambda: False,
    )

    app._observe_host._on_status_items([])

    preview.reload.assert_not_called()
