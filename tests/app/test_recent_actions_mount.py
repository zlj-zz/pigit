# -*- coding: utf-8 -*-
"""
Module: tests/app/test_recent_actions_mount.py
Description: RecentActionsPanel.mount must call Component.mount for render gate.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from unittest.mock import MagicMock

from pigit.app_recent_actions import RecentActionsPanel


def test_mount_sets_is_mounted():
    history = MagicMock()
    history.peek.return_value = []
    panel = RecentActionsPanel(
        history=history,
        git=MagicMock(),
        on_done=lambda: None,
    )
    assert not panel.is_mounted()
    panel.mount()
    assert panel.is_mounted()
    history.peek.assert_called()
