# -*- coding: utf-8 -*-
"""
Tests for pigit.termui P0: semantic keys, escape trie, text single-source.
"""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from pigit.termui import KeyboardInput, keys
from pigit.termui import text as termui_text
from pigit.termui.geometry import TerminalSize
from pigit.termui import wcwidth_table


def test_get_width_plain_are_single_source_with_wcwidth_table():
    assert termui_text.get_width is wcwidth_table.get_width
    assert "pigit.termui.text" in (termui_text.plain.__module__ or "")


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


def test_picker_preview_key_calls_on_preview():
    from pigit.termui.component_list_picker import SearchableListPicker, PickerRow

    calls = []

    def on_confirm(row):
        return 0, None

    def on_preview(row):
        calls.append(row.title)
        return f"would run {row.title}"

    picker = SearchableListPicker(
        [PickerRow(title="a", detail="d", ref=None)],
        title_line="t",
        render_line=lambda r: r.title,
        on_confirm=on_confirm,
        on_preview=on_preview,
        terminal_too_small_msg="",
    )

    class FakeRenderer:
        def __init__(self):
            self.rows = {}
            self._written = []

        def clear_screen(self):
            pass

        def write(self, text):
            self._written.append(text)

        def draw_absolute_row(self, row, text):
            self.rows[row] = text

        def flush(self):
            pass

    picker._renderer = FakeRenderer()
    picker.on_key("?")
    assert calls == ["a"]
    assert picker._renderer.rows  # preview text was drawn


def test_git_branch_completion_candidates(monkeypatch):
    from pigit.cmdparse.completion.base import CompletionType
    from pigit.termui.tty_io import _git_completion_candidates

    class FakeResult:
        stdout = "  main\n* feature\n  remotes/origin/dev\n"

    monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeResult())
    assert _git_completion_candidates(CompletionType.BRANCH) == ["feature", "main", "origin/dev"]


def test_git_file_completion_candidates(monkeypatch):
    from pigit.cmdparse.completion.base import CompletionType
    from pigit.termui.tty_io import _git_completion_candidates

    class FakeStatus:
        stdout = " M src/main.py\n?? README.md\n"

    class FakeLs:
        stdout = "config.yml\n"

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["git", "status"]:
            return FakeStatus()
        return FakeLs()

    monkeypatch.setattr("subprocess.run", fake_run)
    result = _git_completion_candidates(CompletionType.FILE)
    assert "src/main.py" in result
    assert "README.md" in result
    assert "config.yml" in result
