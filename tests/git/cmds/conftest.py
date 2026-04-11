# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/conftest.py
Description: Pytest fixtures for cmd_new tests.
Author: Project Team
Date: 2026-04-10
"""

import pytest

from pigit.git.cmds import (
    CommandRegistry,
    CommandResolver,
    SecureExecutor,
    CommandCategory,
    SecurityLevel,
    CommandMeta,
    CommandDef,
    UserCommandConfig,
)


@pytest.fixture
def fresh_registry():
    """Provide a fresh registry for each test."""
    registry = CommandRegistry()
    registry.clear()
    yield registry
    registry.clear()


@pytest.fixture
def resolver(fresh_registry):
    """Provide a command resolver with fresh registry."""
    return CommandResolver(fresh_registry)


@pytest.fixture
def sample_command_def():
    """Provide a sample command definition."""
    return CommandDef(
        meta=CommandMeta(
            short="test.cmd",
            category=CommandCategory.BRANCH,
            help="Test command",
            examples=["test example"],
        ),
        handler="git test",
    )


@pytest.fixture
def dangerous_command_def():
    """Provide a dangerous command definition."""
    return CommandDef(
        meta=CommandMeta(
            short="test.dangerous",
            category=CommandCategory.BRANCH,
            help="Dangerous test command",
            dangerous=True,
            confirm_msg="Are you sure?",
            security_level=SecurityLevel.DANGEROUS,
        ),
        handler="git dangerous",
    )


@pytest.fixture
def mock_config():
    """Provide a mock user config."""
    config = UserCommandConfig()
    config.aliases = {"tc": "test.cmd"}
    return config
