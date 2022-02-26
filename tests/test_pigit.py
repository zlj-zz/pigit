import pytest
from .utils import analyze_it

from pigit import main


@pytest.mark.parametrize(
    "command",
    [
        "--report",
        "--config",  # git config
        "--information",  # git information
        "--count",  # code counter
        "--create-config",
        "cmd -h",
        "cmd ws",
        "cmd -t",
        "repo ll",
    ],
)
def test_color_command(command: str):
    print()
    main(command)
