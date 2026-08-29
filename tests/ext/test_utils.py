# -*- coding: utf-8 -*-
"""
Module: tests/ext/test_utils.py
Description: Nerd Font detection (resolve_nerd_icons) and icon fallback (resolve_icon).
Author: Zev
Date: 2026-08-29
"""

from __future__ import annotations

from pigit.ext.utils import (
    _FALLBACK_DIR,
    _FALLBACK_FILE,
    resolve_icon,
    resolve_nerd_icons,
)
from pigit.termui.wcwidth_table import wcswidth

# ── resolve_nerd_icons ──


def test_resolve_nerd_icons_on_and_off_force():
    assert resolve_nerd_icons("on", env={}) is True
    assert resolve_nerd_icons("off", env={"KITTY_WINDOW_ID": "1"}) is False


def test_resolve_nerd_icons_auto_no_markers_falls_back():
    assert resolve_nerd_icons("auto", env={}) is False
    assert resolve_nerd_icons("auto", env={"TERM": "xterm-256color"}) is False


def test_resolve_nerd_icons_auto_kitty_marker():
    assert resolve_nerd_icons("auto", env={"KITTY_WINDOW_ID": "123"}) is True


def test_resolve_nerd_icons_auto_wezterm_marker():
    assert (
        resolve_nerd_icons("auto", env={"WEZTERM_EXECUTABLE": "/bin/wezterm"}) is True
    )


def test_resolve_nerd_icons_auto_alacritty_marker():
    assert resolve_nerd_icons("auto", env={"ALACRITTY_WINDOW_ID": "1"}) is True


def test_resolve_nerd_icons_auto_ghostty_marker():
    assert resolve_nerd_icons("auto", env={"GHOSTTY_RESOURCES_DIR": "/x"}) is True


def test_resolve_nerd_icons_auto_term_program_known():
    assert resolve_nerd_icons("auto", env={"TERM_PROGRAM": "WezTerm"}) is True
    assert resolve_nerd_icons("auto", env={"TERM_PROGRAM": "ghostty"}) is True
    assert resolve_nerd_icons("auto", env={"TERM_PROGRAM": "kitty"}) is True
    assert resolve_nerd_icons("auto", env={"TERM_PROGRAM": "Apple_Terminal"}) is False


def test_resolve_nerd_icons_defaults_to_os_environ(monkeypatch):
    monkeypatch.delenv("KITTY_WINDOW_ID", raising=False)
    monkeypatch.delenv("WEZTERM_EXECUTABLE", raising=False)
    monkeypatch.delenv("ALACRITTY_WINDOW_ID", raising=False)
    monkeypatch.delenv("GHOSTTY_RESOURCES_DIR", raising=False)
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    assert resolve_nerd_icons("auto") is False


# ── resolve_icon ──


def test_resolve_icon_nerd_dir_and_file():
    assert resolve_icon(True, "Python", is_dir=True) == "\uf07b"
    assert resolve_icon(True, "Python") == "\ue606"


def test_resolve_icon_fallback_dir_and_file():
    assert resolve_icon(False, "Python", is_dir=True) == _FALLBACK_DIR
    assert resolve_icon(False, "Python") == _FALLBACK_FILE


def test_fallback_symbols_are_single_cell():
    """S1: A-class glyphs must stay 1 cell so row alignment cannot drift."""
    assert wcswidth(_FALLBACK_DIR) == 1
    assert wcswidth(_FALLBACK_FILE) == 1
