# -*- coding: utf-8 -*-
"""
Tests for pigit.termui P0: semantic keys, escape trie, text single-source.
"""

from __future__ import annotations

import sys
from unittest import mock

import pytest

import pigit.tui.utils as tui_utils
from pigit.termui import KeyboardInput, keys
from pigit.termui import text as termui_text
from pigit.termui.geometry import TerminalSize


def test_get_width_plain_are_single_source_with_tui_utils():
    assert termui_text.get_width is tui_utils.get_width
    assert termui_text.plain is tui_utils.plain


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
def test_golden_byte_sequences(raw: bytes, expected: list):
    def read_hook(_timeout: float) -> bytes:
        return raw

    kb = KeyboardInput(read_hook=read_hook)
    assert kb.read_keys(timeout=0.01) == expected


def test_lone_esc_emitted_after_timeout():
    chunks = [b"\x1b", b""]

    def read_hook(_timeout: float) -> bytes:
        return chunks.pop(0) if chunks else b""

    kb = KeyboardInput(read_hook=read_hook)
    assert kb.read_keys(0.01) == []
    assert kb.read_keys(0.01) == ["esc"]


def test_utf8_printable():
    raw = "界".encode("utf-8")

    def read_hook(_timeout: float) -> bytes:
        return raw

    kb = KeyboardInput(read_hook=read_hook)
    assert kb.read_keys(0.01) == ["界"]


def test_window_resize_emitted_when_columns_change():
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
def test_windows_arrow_mapping():
    def read_hook(_timeout: float) -> bytes:
        return b"\xe0H"

    kb = KeyboardInput(read_hook=read_hook)
    assert kb.read_keys(0.01) == ["up"]
