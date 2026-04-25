# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_input_keyboard.py
Description: Tests for KeyboardInput byte parsing and semantic key emission.
Author: Zev
Date: 2026-04-18
"""

import sys
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from pigit.termui._geometry import TerminalSize
from pigit.termui.input_keyboard import KeyboardInput
from pigit.termui import keys


class TestKeyboardInputConsume:
    def test_parse_single_byte_char(self):
        ki = KeyboardInput()
        ki._buffer = bytearray(b"a")
        key, n = ki._consume_one()
        assert key == "a"
        assert n == 1
        assert len(ki._buffer) == 0

    def test_parse_escape_sequence_arrow(self):
        ki = KeyboardInput()
        ki._buffer = bytearray(b"\x1b[A")
        key, n = ki._consume_one()
        assert key == keys.KEY_UP
        assert n == 3

    def test_parse_ctrl_combo(self):
        ki = KeyboardInput()
        ki._buffer = bytearray(b"\x03")  # Ctrl+C
        key, n = ki._consume_one()
        assert key == "ctrl c"
        assert n == 1

    def test_parse_unknown_escape_fallback(self):
        """Unrecognized but complete CSI sequence is consumed and dropped."""
        ki = KeyboardInput()
        ki._buffer = bytearray(b"\x1b[X")
        key, n = ki._consume_one()
        assert key is None
        assert n == 3
        assert len(ki._buffer) == 0

    def test_parse_tab(self):
        ki = KeyboardInput()
        ki._buffer = bytearray(b"\t")
        key, n = ki._consume_one()
        assert key == keys.KEY_TAB
        assert n == 1

    def test_parse_enter(self):
        ki = KeyboardInput()
        ki._buffer = bytearray(b"\r")
        key, n = ki._consume_one()
        assert key == keys.KEY_ENTER
        assert n == 1

    def test_parse_backspace(self):
        ki = KeyboardInput()
        ki._buffer = bytearray(b"\x7f")
        key, n = ki._consume_one()
        assert key == keys.KEY_BACKSPACE
        assert n == 1

    def test_parse_esc_alone_needs_more(self):
        ki = KeyboardInput()
        ki._buffer = bytearray(b"\x1b")
        key, n = ki._consume_one()
        # Lone ESC is incomplete; read_keys promotes it to ESC on timeout
        assert key is None
        assert n == 0

    def test_parse_utf8_multibyte(self):
        ki = KeyboardInput()
        ki._buffer = bytearray("中".encode("utf-8"))
        key, n = ki._consume_one()
        assert key == "中"
        assert n == 3

    def test_parse_utf8_incomplete_waits(self):
        ki = KeyboardInput()
        # First byte of a 3-byte UTF-8 sequence for "中"
        ki._buffer = bytearray(b"\xe4")
        key, n = ki._consume_one()
        assert key is None
        assert n == 0

    def test_parse_high_byte_invalid_utf8(self):
        ki = KeyboardInput()
        # Invalid UTF-8: 0xFF is not a valid start byte
        ki._buffer = bytearray(b"\xff")
        key, n = ki._consume_one()
        assert key == "\xff"
        assert n == 1

    def test_parse_windows_extended_key(self):
        ki = KeyboardInput()
        # Simulate windows extended key: prefix + second byte
        ki._buffer = bytearray(b"\x00\x48")
        with patch("sys.platform", "win32"):
            key, n = ki._consume_one()
        # May or may not be mapped depending on WIN_EXT_TO_SEMANTIC
        assert n == 2


class TestKeyboardInputReadKeys:
    def test_read_with_timeout_returns_empty(self):
        ki = KeyboardInput()
        ki._read_chunk = MagicMock(return_value=b"")
        result = ki.read_keys(timeout=0.01)
        assert result == []

    def test_read_single_key(self):
        ki = KeyboardInput()
        ki._read_chunk = MagicMock(return_value=b"x")
        result = ki.read_keys(timeout=0.01)
        assert result == ["x"]

    def test_read_multiple_keys(self):
        ki = KeyboardInput()
        ki._read_chunk = MagicMock(return_value=b"abc")
        result = ki.read_keys(timeout=0.01)
        assert result == ["a", "b", "c"]

    def test_read_arrow_sequence(self):
        ki = KeyboardInput()
        ki._read_chunk = MagicMock(return_value=b"\x1b[B")
        result = ki.read_keys(timeout=0.01)
        assert result == [keys.KEY_DOWN]

    def test_read_mixed_sequence(self):
        ki = KeyboardInput()
        ki._read_chunk = MagicMock(return_value=b"a\x1b[Cb")
        result = ki.read_keys(timeout=0.01)
        assert result == ["a", keys.KEY_RIGHT, "b"]

    def test_read_esc_on_timeout(self):
        """Lone ESC byte buffered and then timed out is emitted as esc."""
        ki = KeyboardInput()
        ki._read_chunk = MagicMock(return_value=b"")
        ki._buffer = bytearray(b"\x1b")
        result = ki.read_keys(timeout=0.01)
        assert result == [keys.KEY_ESC]
        assert len(ki._buffer) == 0

    def test_read_ctrl_combo(self):
        ki = KeyboardInput()
        ki._read_chunk = MagicMock(return_value=b"\x01")  # Ctrl+A
        result = ki.read_keys(timeout=0.01)
        assert result == ["ctrl a"]

    @patch("pigit.termui.input_keyboard.TerminalSize.from_os")
    def test_read_resize_event(self, mock_from_os):
        from pigit.termui._geometry import TerminalSize

        mock_from_os.side_effect = [
            TerminalSize(80, 24),
            TerminalSize(100, 40),
        ]
        ki = KeyboardInput()
        ki._read_chunk = MagicMock(return_value=b"")
        # First call establishes baseline
        ki.read_keys(timeout=0.01)
        # Second call detects change
        result = ki.read_keys(timeout=0.01)
        assert keys.KEY_WINDOW_RESIZE in result

    def test_read_windows_path(self):
        """Coverage for _read_chunk_windows branch via mock."""
        import sys
        mock_msvcrt = MagicMock()
        mock_msvcrt.kbhit.side_effect = [True, False]
        mock_msvcrt.getch.return_value = b"x"
        sys.modules["msvcrt"] = mock_msvcrt
        try:
            ki = KeyboardInput()
            ki._read_chunk = ki._read_chunk_windows
            result = ki.read_keys(timeout=0.01)
            assert result == ["x"]
        finally:
            del sys.modules["msvcrt"]

    def test_default_stdin_returns_buffer(self):
        ki = KeyboardInput()
        buf = ki._default_stdin()
        assert buf is not None

    def test_read_chunk_posix_timeout(self):
        ki = KeyboardInput()
        with patch("select.select") as mock_select:
            mock_select.return_value = ([], [], [])
            result = ki._read_chunk_posix(timeout=0.01)
        assert result == b""

    def test_read_chunk_posix_with_data(self):
        ki = KeyboardInput()
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0
        ki._stdin = mock_stdin
        with patch("select.select") as mock_select, \
             patch("os.read") as mock_read:
            mock_select.return_value = ([mock_stdin], [], [])
            mock_read.return_value = b"abc"
            result = ki._read_chunk_posix(timeout=0.01)
        assert result == b"abc"

    def test_read_chunk_posix_interrupted_then_ready(self):
        ki = KeyboardInput()
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0
        ki._stdin = mock_stdin
        with patch("select.select") as mock_select, \
             patch("os.read") as mock_read:
            mock_select.side_effect = [InterruptedError, ([mock_stdin], [], [])]
            mock_read.return_value = b"x"
            result = ki._read_chunk_posix(timeout=0.01)
        assert result == b"x"

    def test_read_chunk_posix_blocking_io_error(self):
        ki = KeyboardInput()
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0
        ki._stdin = mock_stdin
        with patch("select.select") as mock_select, \
             patch("os.read") as mock_read:
            mock_select.return_value = ([mock_stdin], [], [])
            mock_read.side_effect = BlockingIOError
            result = ki._read_chunk_posix(timeout=0.01)
        assert result == b""

    def test_drain_buffer_skips_none_keys(self):
        """Coverage for _drain_buffer when _consume_one returns (None, n)."""
        ki = KeyboardInput()
        ki._buffer = bytearray(b"\x1b[X")
        out = ki._drain_buffer()
        # Unknown escape is consumed but yields no key
        assert out == []
        assert len(ki._buffer) == 0

    def test_utf8_4_byte_sequence(self):
        ki = KeyboardInput()
        # U+1F600 (😀) is 4 bytes in UTF-8
        ki._buffer = bytearray("😀".encode("utf-8"))
        key, n = ki._consume_one()
        assert key == "😀"
        assert n == 4

    def test_utf8_decode_error_fallback(self):
        ki = KeyboardInput()
        # Invalid 2-byte sequence: 0xC0 0x80 is overlong encoding
        ki._buffer = bytearray(b"\xc0\x80")
        key, n = ki._consume_one()
        assert key == "\xc0"
        assert n == 2


class TestKeyboardInputGoldenSequences:
    """End-to-end read_keys tests via read_hook injection."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            (b"a", ["a"]),
            (b"X", ["X"]),
            (b"\t", ["tab"]),
            (b"\r", ["enter"]),
            (b"\n", ["enter"]),
            (b"\x7f", ["backspace"]),
            (b"\x03", ["ctrl c"]),
            (b"\x1b[A", ["up"]),
            (b"\x1b[B", ["down"]),
            (b"\x1b[C", ["right"]),
            (b"\x1b[D", ["left"]),
            (b"\x1b[5~", ["page up"]),
            (b"\x1b[6~", ["page down"]),
            (b"\x1bOP", ["f1"]),
        ],
    )
    def test_golden_byte_sequences(self, raw: bytes, expected: list):
        def read_hook(_timeout: float) -> bytes:
            return raw

        kb = KeyboardInput(read_hook=read_hook)
        assert kb.read_keys(timeout=0.01) == expected

    def test_lone_esc_emitted_after_timeout(self):
        chunks = [b"\x1b", b""]

        def read_hook(_timeout: float) -> bytes:
            return chunks.pop(0) if chunks else b""

        kb = KeyboardInput(read_hook=read_hook)
        assert kb.read_keys(0.01) == []
        assert kb.read_keys(0.01) == ["esc"]

    def test_utf8_printable(self):
        raw = "界".encode("utf-8")

        def read_hook(_timeout: float) -> bytes:
            return raw

        kb = KeyboardInput(read_hook=read_hook)
        assert kb.read_keys(0.01) == ["界"]

    def test_window_resize_emitted_when_columns_change(self):
        with mock.patch(
            "pigit.termui.input_keyboard.TerminalSize.from_os",
            side_effect=[
                TerminalSize(80, 24),
                TerminalSize(80, 24),
                TerminalSize(100, 24),
            ],
        ):
            kb = KeyboardInput(read_hook=lambda _t: b"")
            kb.read_keys(0.01)
            assert kb.read_keys(0.01) == []
            assert kb.read_keys(0.01) == [keys.KEY_WINDOW_RESIZE]

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows extended-key mapping")
    def test_windows_arrow_mapping(self):
        def read_hook(_timeout: float) -> bytes:
            return b"\xe0H"

        kb = KeyboardInput(read_hook=read_hook)
        assert kb.read_keys(0.01) == ["up"]
