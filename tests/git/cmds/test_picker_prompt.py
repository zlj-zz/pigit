# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_picker_prompt.py
Description: Tests for ArgumentPrompter.
Author: Zev
Date: 2026-04-15
"""

from unittest import mock

from pigit.git.cmds._picker_prompt import ArgumentPrompter, _dim_hint


def test_dim_hint_applies_ansi():
    assert _dim_hint("hint") == "\033[2mhint\033[0m"


def test_prompter_shows_cursor_before_read(monkeypatch):
    renderer = mock.Mock()
    writes = []
    flushes = []

    def fake_flush():
        flushes.append(True)

    prompter = ArgumentPrompter(renderer, writes.append, fake_flush)

    monkeypatch.setattr(
        "pigit.git.cmds._picker_prompt.read_line_cancellable",
        lambda *, write, flush, prompt: "value",
    )

    result = prompter.prompt("b.c", None)
    assert result == "value"
    assert renderer.show_cursor.called
    assert renderer.hide_cursor.called


def test_prompter_delegates_to_completion_reader(monkeypatch):
    renderer = mock.Mock()
    writes = []
    flushes = []

    def fake_flush():
        flushes.append(True)

    prompter = ArgumentPrompter(renderer, writes.append, fake_flush)

    captured = {}

    def fake_read_line(*, write, flush, prompt, candidate_provider, hint_styler=None):
        captured["provider"] = candidate_provider
        captured["styler"] = hint_styler
        return "main"

    monkeypatch.setattr(
        "pigit.git.cmds._picker_prompt.read_line_with_completion",
        fake_read_line,
    )

    def provider(prefix):
        return ["main", "master"]

    result = prompter.prompt("b.d", provider)
    assert result == "main"
    assert captured["provider"] is provider
    assert captured["styler"] is _dim_hint


def test_prompter_delegates_to_cancellable_reader(monkeypatch):
    renderer = mock.Mock()

    def fake_write(s):
        pass

    def fake_flush():
        pass

    prompter = ArgumentPrompter(renderer, fake_write, fake_flush)

    captured = {}

    def fake_read_line(*, write, flush, prompt):
        captured["used"] = True
        return "value"

    monkeypatch.setattr(
        "pigit.git.cmds._picker_prompt.read_line_cancellable",
        fake_read_line,
    )

    result = prompter.prompt("custom", None)
    assert result == "value"
    assert captured.get("used") is True
