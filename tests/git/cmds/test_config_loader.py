# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_config_loader.py
Description: Tests for cmd_new config loader.
Author: Project Team
Date: 2026-04-10
"""

import pytest
import tempfile
import os
from pathlib import Path

from pigit.git.cmds import (
    UserCommandConfig,
    ScriptConfig,
    load_user_config,
    CommandCategory,
    CommandSource,
)


class TestUserCommandConfig:
    def test_default_creation(self):
        config = UserCommandConfig()
        assert config.aliases == {}
        assert config.overrides == {}
        assert config.settings == {}

    def test_with_values(self):
        config = UserCommandConfig(
            aliases={"st": "w.s"},
            overrides={"b.d": "custom_delete"},
            settings={"confirm_dangerous": False},
        )
        assert config.aliases["st"] == "w.s"
        assert config.overrides["b.d"] == "custom_delete"
        assert config.settings["confirm_dangerous"] is False

    def test_get_alias(self):
        config = UserCommandConfig(aliases={"st": "w.s"})
        assert config.get_alias("st") == "w.s"
        assert config.get_alias("unknown") is None

    def test_has_override(self):
        config = UserCommandConfig(overrides={"b.d": "custom"})
        assert config.has_override("b.d") is True
        assert config.has_override("unknown") is False

    def test_get_override(self):
        config = UserCommandConfig(overrides={"b.d": "custom"})
        assert config.get_override("b.d") == "custom"
        assert config.get_override("unknown") is None

    def test_get_script(self):
        script = ScriptConfig(steps=["b.o test", "p", "m main"])
        config = UserCommandConfig(scripts={"update_test": script})
        assert config.get_script("update_test") == script
        assert config.get_script("unknown") is None

    def test_has_script(self):
        script = ScriptConfig(steps=["b.o test"])
        config = UserCommandConfig(scripts={"update_test": script})
        assert config.has_script("update_test") is True
        assert config.has_script("unknown") is False

    def test_to_command_defs(self):
        script = ScriptConfig(
            steps=["b.o test", "p"],
            help="Update test branch",
            category="branch",
            dangerous=True,
            confirm_msg="Continue?",
            examples=["update_test --rebase"],
        )
        config = UserCommandConfig(
            aliases={"st": "w.s"},
            scripts={"update_test": script},
        )

        commands = config.to_command_defs()
        assert len(commands) == 2

        # Find alias command
        alias_cmd = next(c for c in commands if c.meta.short == "st")
        assert alias_cmd.meta.category == CommandCategory.ALIAS
        assert alias_cmd.meta.source == CommandSource.ALIAS
        assert alias_cmd.meta.is_user_defined is True
        assert alias_cmd.handler == "w.s"

        # Find script command
        script_cmd = next(c for c in commands if c.meta.short == "update_test")
        assert script_cmd.meta.category == CommandCategory.BRANCH
        assert script_cmd.meta.source == CommandSource.SCRIPT
        assert script_cmd.meta.is_user_defined is True
        assert script_cmd.meta.dangerous is True
        assert script_cmd.meta.help == "Update test branch"


class TestLoadUserConfig:
    def test_load_from_nonexistent_file(self):
        config = UserCommandConfig.from_toml("/nonexistent/path.conf")
        assert config.aliases == {}

    def test_load_valid_toml(self):
        toml_content = """
[cmd_new]
confirm_dangerous = false
show_command = true

[cmd_new.aliases]
st = "w.s"
ci = "c"
co = "c.o"

[cmd_new.overrides]
"b.d" = "safe_delete"

[cmd_new.settings]
confirm_dangerous = false
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            config = UserCommandConfig.from_toml(temp_path)
            assert config.aliases["st"] == "w.s"
            assert config.aliases["ci"] == "c"
            assert config.settings.get("confirm_dangerous") is False
        finally:
            os.unlink(temp_path)

    def test_load_scripts_concise_form(self):
        """Test loading scripts in concise form (inline array)."""
        toml_content = """
[cmd_new.scripts]
update_test = ["b.o test", "p", "m main"]
deploy = ["!:npm run build", "!:npm run deploy"]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            config = UserCommandConfig.from_toml(temp_path)
            assert "update_test" in config.scripts
            script = config.scripts["update_test"]
            assert isinstance(script, ScriptConfig)
            assert script.steps == ["b.o test", "p", "m main"]
            assert script.category == "script"  # default
            assert script.dangerous is False  # default
        finally:
            os.unlink(temp_path)

    def test_load_scripts_full_form(self):
        """Test loading scripts in full form (table with metadata)."""
        toml_content = '''
[cmd_new.scripts.update_test]
steps = ["!:export SAVED_BRANCH=$(git branch --show-current)", "b.o test", "p", "m $SAVED_BRANCH"]
help = "Update test branch with current branch changes"
category = "branch"
dangerous = false
confirm_msg = ""
examples = ["cmd_new update_test", "cmd_new update_test --rebase"]

[cmd_new.scripts.deploy]
steps = ["!:npm run build", "!:npm run deploy"]
help = "Build and deploy the application"
category = "settings"
dangerous = true
confirm_msg = "This will deploy to production. Continue?"
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            config = UserCommandConfig.from_toml(temp_path)

            # Check update_test script
            update_test = config.scripts["update_test"]
            assert isinstance(update_test, ScriptConfig)
            assert update_test.help == "Update test branch with current branch changes"
            assert update_test.category == "branch"
            assert update_test.dangerous is False
            assert len(update_test.examples) == 2

            # Check deploy script
            deploy = config.scripts["deploy"]
            assert deploy.category == "settings"
            assert deploy.dangerous is True
            assert deploy.confirm_msg == "This will deploy to production. Continue?"
        finally:
            os.unlink(temp_path)

    def test_default_path_unix(self, monkeypatch):
        if os.name == "nt":
            pytest.skip("Unix-only test")

        monkeypatch.setenv("HOME", "/home/testuser")
        path = UserCommandConfig.default_path()
        assert str(path) == "/home/testuser/.config/pigit/pigit.cmds.toml"

    def test_default_path_windows(self, monkeypatch):
        if os.name != "nt":
            pytest.skip("Windows-only test")

        monkeypatch.setenv("USERPROFILE", "C:\\Users\\TestUser")
        path = UserCommandConfig.default_path()
        assert "pigit.conf" in str(path)


class TestLoadUserConfigFunction:
    def test_load_with_custom_path(self):
        toml_content = '[cmd_new.aliases]\nst = "w.s"'

        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            config = load_user_config(temp_path)
            assert config.aliases["st"] == "w.s"
        finally:
            os.unlink(temp_path)
