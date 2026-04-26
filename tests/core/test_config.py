from unittest.mock import patch

import pytest

from pigit.config import Config
from pigit.config_data import ConfigData

from paths import TEST_CONFIG


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    """Reset Config singleton between tests."""
    Config._instances.clear()
    yield
    Config._instances.clear()


@patch("builtins.input", lambda _: "yes")
def test_create(tmp_path):
    config_path = tmp_path / "pigit-create.toml"
    assert Config(
        str(config_path),
        version="test",
        auto_load=False,
    ).create_config_template()
    assert config_path.exists()
    content = config_path.read_text(encoding="utf-8")
    assert 'version = "test"' in content
    assert "[cmd]" in content
    assert "[counter]" in content


def test_load():
    c = Config(
        TEST_CONFIG,
        version="test",
        auto_load=True,
    )
    data = c.get()
    assert data.cmd.display is False
    assert data.cmd.recommend is False
    assert data.counter.use_gitignore is False
    assert data.counter.show_invalid is True
    assert data.counter.show_icon is True
    assert data.counter.format == "simple"
    assert data.info.git_config_format == "normal"
    assert data.info.repo_include == ["path", "remote"]
    assert data.repo.auto_append is False
    assert data.log.debug is True
    assert data.log.output is True


def test_output_warnings():
    c = Config(
        TEST_CONFIG,
        version="test",
        auto_load=True,
    ).output_warnings()
    data = c.get()
    assert isinstance(data, ConfigData)


def test_default_values_when_no_config_file():
    c = Config(
        "/nonexistent/path/pigit.toml",
        version="test",
        auto_load=True,
    )
    data = c.get()
    assert data.cmd.display is True
    assert data.cmd.recommend is True
    assert data.counter.use_gitignore is True
    assert data.counter.format == "table"
    assert data.info.git_config_format == "table"
    assert data.info.repo_include == ["remote", "branch", "log"]
    assert data.repo.auto_append is True
    assert data.log.debug is False
    assert data.log.output is False


def test_invalid_format_falls_back_to_default(tmp_path):
    config_path = tmp_path / "pigit-invalid.toml"
    config_path.write_text(
        "\n".join(
            [
                'version = "test"',
                "",
                "[counter]",
                'format = "invalid"',
                "",
                "[info]",
                'git_config_format = "invalid"',
            ]
        ),
        encoding="utf-8",
    )

    c = Config(
        str(config_path),
        version="test",
        auto_load=True,
    )
    data = c.get()
    assert data.counter.format == "table"
    assert data.info.git_config_format == "table"
    assert any("counter.format" in w for w in c._warnings)
    assert any("git_config_format" in w for w in c._warnings)


def test_toml_read_with_comments_and_inline_strings(tmp_path):
    config_path = tmp_path / "pigit-comment.toml"
    config_path.write_text(
        "\n".join(
            [
                "#? Config file for pigit v. test",
                "# full line comment",
                'version = "test"',
                "",
                "[cmd]",
                "display = true",
                "recommend = false",
                "",
                "[info]",
                'repo_include = ["path#hash", "remote"]',
            ]
        ),
        encoding="utf-8",
    )

    c = Config(
        str(config_path),
        version="test",
        auto_load=True,
    )
    data = c.get()
    assert data.cmd.display is True
    assert data.cmd.recommend is False
    assert data.info.repo_include == ["path#hash", "remote"]
