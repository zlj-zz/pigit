# -*- coding: utf-8 -*-
"""
Contract tests for ``TermuiInputBridge`` and related termui input helpers
(replaces coverage that targeted removed ``legacy_input.PosixInput``).
"""

from __future__ import annotations

import math
import pytest
from unittest.mock import patch

from pigit.termui.keys import is_mouse_event
from pigit.termui.tui_input_bridge import TermuiInputBridge


@pytest.mark.parametrize(
    "ev, expected",
    [
        (("mouse press", 1, 0, 0), True),
        (("meta mouse drag", 0, 0, 0), True),
        (("click", 1, 0, 0), False),
        ((), False),
        ((1, 2, 3), False),
        ("up", False),
    ],
)
def test_is_mouse_event(ev, expected):
    assert is_mouse_event(ev) is expected


def test_termui_input_bridge_forwards_read_keys():
    bridge = TermuiInputBridge()
    with patch.object(
        bridge._kb,
        "read_keys",
        return_value=["j", "enter"],
    ) as mock_read:
        keys, _raw = bridge.get_input()
    mock_read.assert_called_once()
    assert keys == ["j", "enter"]


@pytest.mark.parametrize(
    "bad",
    [
        -1.0,
        float("nan"),
        float("inf"),
    ],
)
def test_termui_input_bridge_rejects_invalid_timeout(bad):
    bridge = TermuiInputBridge()
    with pytest.raises(ValueError, match="non-negative finite"):
        bridge.set_input_timeouts(bad)


def test_termui_input_bridge_ignores_none_timeout():
    bridge = TermuiInputBridge()
    bridge.set_input_timeouts(0.5)
    bridge.set_input_timeouts(None)
    assert bridge._timeout == 0.5


def test_termui_input_bridge_accepts_zero_timeout():
    bridge = TermuiInputBridge()
    bridge.set_input_timeouts(0.0)
    assert bridge._timeout == 0.0
    assert math.isfinite(bridge._timeout)
