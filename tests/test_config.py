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
