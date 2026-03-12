from unittest.mock import patch

from pigit.config import Config

from .conftest import TEST_PATH


TEST_CONFIG = f"{TEST_PATH}/pigit.conf"


@patch("builtins.input", lambda _: "yes")
def test_create():
    assert (
        Config(
            TEST_CONFIG,
            version="test",
            auto_load=False,
        ).create_config_template()
        == True
    )


def test_load():
    c = Config(
        TEST_CONFIG,
        version="test",
        auto_load=True,
    ).output_warnings()
    print(c.conf)


def test_list_config_uses_literal_eval():
    c = Config(
        TEST_CONFIG,
        version="test",
        auto_load=False,
    )
    c.conf = {}
    c._warnings = []

    c.check_and_set_value("repo_info_include", '["path", "remote"]', c.conf)

    assert c.conf["repo_info_include"] == ["path", "remote"]
    assert c._warnings == []


def test_list_config_rejects_non_literal_expression():
    c = Config(
        TEST_CONFIG,
        version="test",
        auto_load=False,
    )
    c.conf = {}
    c._warnings = []

    c.check_and_set_value(
        "repo_info_include",
        '[__import__("os").system("echo hacked")]',
        c.conf,
    )

    assert "repo_info_include" not in c.conf
    assert any("invalid list literal" in warning for warning in c._warnings)
