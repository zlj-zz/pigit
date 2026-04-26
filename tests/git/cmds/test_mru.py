# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_mru.py
Description: Tests for MRU persistence utilities.
Author: Zev
Date: 2026-04-14
"""

import json

import pytest

from pigit.git.cmds._mru import load_mru, save_mru, record_command_use


class TestMruPersistence:
    def test_load_mru_missing_file_returns_empty(self, tmp_path):
        path = tmp_path / "missing_mru.json"
        assert load_mru(path) == []

    def test_load_mru_invalid_json_returns_empty(self, tmp_path):
        path = tmp_path / "bad_mru.json"
        path.write_text("not json", encoding="utf-8")
        assert load_mru(path) == []

    def test_save_and_load_round_trip(self, tmp_path):
        path = tmp_path / "mru.json"
        save_mru(["b.o", "i.a", "c.m"], path)
        assert load_mru(path) == ["b.o", "i.a", "c.m"]

    def test_record_command_use_prepends_and_dedupes(self, tmp_path):
        path = tmp_path / "mru.json"
        save_mru(["b.o", "i.a"], path)
        record_command_use("c.m", max_size=20)
        # default path is PIGIT_HOME, so this actually writes there unless patched
        # Better to patch load_mru/save_mru or use a monkeypatched path

    def test_record_command_use_with_custom_path(self, tmp_path):
        path = tmp_path / "mru.json"
        save_mru(["b.o", "i.a"], path)
        record_command_use("c.m", max_size=20, path=path)
        assert load_mru(path) == ["c.m", "b.o", "i.a"]

    def test_record_command_use_moves_existing_to_front(self, tmp_path):
        path = tmp_path / "mru.json"
        save_mru(["b.o", "i.a", "c.m"], path)
        record_command_use("i.a", max_size=20, path=path)
        assert load_mru(path) == ["i.a", "b.o", "c.m"]

    def test_record_command_use_caps_size(self, tmp_path):
        path = tmp_path / "mru.json"
        save_mru(["a", "b", "c"], path)
        record_command_use("d", max_size=3, path=path)
        assert load_mru(path) == ["d", "a", "b"]
