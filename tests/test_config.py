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


def test_read_config_parse_inline_comments_and_hash_in_string(tmp_path):
    config_path = tmp_path / "pigit-inline-comment.conf"
    config_path.write_text(
        "\n".join(
            [
                "#? Config file for pigit v. test",
                "# full line comment",
                "cmd_display=true",
                "cmd_recommend=false # line-end comment",
                'counter_format="simple"',
                'repo_info_include=["path#hash", "remote"] # keep hash in string',
            ]
        ),
        encoding="utf-8",
    )

    c = Config(
        TEST_CONFIG,
        version="test",
        auto_load=False,
    )
    c.config_file_path = str(config_path)
    c.conf = {}
    c._warnings = []

    c.read_config()

    assert c.conf["cmd_display"] is True
    assert c.conf["cmd_recommend"] is False
    assert c.conf["counter_format"] == "simple"
    assert c.conf["repo_info_include"] == ["path#hash", "remote"]
