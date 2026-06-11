# -*- coding: utf-8 -*-
"""
Contract tests for ``TermuiInputBridge`` and related termui input helpers
(replaces coverage that targeted removed ``legacy_input.PosixInput``).
"""

from __future__ import annotations

import pytest
import termios
from unittest.mock import patch

from pigit.termui.keys import is_mouse_event
from pigit.termui.input import TermuiInputBridge


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


def test_termui_input_bridge_start_stop_noop():
    bridge = TermuiInputBridge()
    bridge.start()
    bridge.stop()


class TestInputTerminal:
    # NOTE: termios control-character indices (VINTR, VQUIT, etc.) vary by
    # platform (e.g. VINTR is 8 on Darwin but 0 on Linux). Always use the
    # ``termios`` module constants instead of hard-coded numbers.

    def test_get_input_raises_not_implemented(self):
        from pigit.termui.input import InputTerminal

        term = InputTerminal()
        with pytest.raises(NotImplementedError, match="Subclasses must implement"):
            term.get_input()

    def test_tty_signal_keys_returns_early_on_non_tty(self):
        from pigit.termui.input import InputTerminal

        term = InputTerminal()
        with patch("os.isatty", return_value=False):
            result = term.tty_signal_keys(fileno=0)
        assert result is None

    def test_tty_signal_keys_reads_current_settings(self):
        from pigit.termui.input import InputTerminal

        term = InputTerminal()
        cc = [0] * 32
        cc[termios.VINTR] = 3
        cc[termios.VQUIT] = 28
        cc[termios.VSTART] = 17
        cc[termios.VSTOP] = 19
        cc[termios.VSUSP] = 26
        fake_tattr = [[], [], [], [], [], [], cc]
        with (
            patch("os.isatty", return_value=True),
            patch(
                "pigit.termui.input.termios.tcgetattr", return_value=fake_tattr
            ) as mock_getattr,
        ):
            result = term.tty_signal_keys(fileno=0)
        mock_getattr.assert_called_once()
        assert result == (3, 28, 17, 19, 26)

    def test_tty_signal_keys_sets_undefined_to_zero(self):
        from pigit.termui.input import InputTerminal

        term = InputTerminal()
        cc = [0] * 32
        cc[termios.VINTR] = 3
        fake_tattr = [[], [], [], [], [], [], cc]
        with (
            patch("os.isatty", return_value=True),
            patch("pigit.termui.input.termios.tcgetattr", return_value=fake_tattr),
            patch("pigit.termui.input.termios.tcsetattr") as mock_setattr,
        ):
            term.tty_signal_keys(intr="undefined", fileno=0)
        assert mock_setattr.called
        call_tattr = mock_setattr.call_args[0][2]
        assert call_tattr[6][termios.VINTR] == 0

    def test_tty_signal_keys_sets_explicit_values(self):
        from pigit.termui.input import InputTerminal

        term = InputTerminal()
        cc = [0] * 32
        cc[termios.VINTR] = 3
        cc[termios.VQUIT] = 28
        fake_tattr = [[], [], [], [], [], [], cc]
        with (
            patch("os.isatty", return_value=True),
            patch("pigit.termui.input.termios.tcgetattr", return_value=fake_tattr),
            patch("pigit.termui.input.termios.tcsetattr") as mock_setattr,
        ):
            term.tty_signal_keys(intr=5, quit=6, fileno=0)
        call_tattr = mock_setattr.call_args[0][2]
        assert call_tattr[6][termios.VINTR] == 5
        assert call_tattr[6][termios.VQUIT] == 6

    def test_tty_signal_keys_no_change_returns_without_setting(self):
        from pigit.termui.input import InputTerminal

        term = InputTerminal()
        cc = [0] * 32
        cc[termios.VINTR] = 3
        fake_tattr = [[], [], [], [], [], [], cc]
        with (
            patch("os.isatty", return_value=True),
            patch("pigit.termui.input.termios.tcgetattr", return_value=fake_tattr),
            patch("pigit.termui.input.termios.tcsetattr") as mock_setattr,
        ):
            term.tty_signal_keys(fileno=0)
        mock_setattr.assert_not_called()
