import sys

sys.path.insert(0, ".")

import pytest
from pyinstrument import Profiler

from pigit.command_processor import GitProcessor
from pigit.common import Fx


def test_init():
    with pytest.raises(TypeError):
        GitProcessor(extra_cmds="xxx")


@pytest.fixture(scope="module")
def setup():
    extra = {"aa": {"help": "print system user name."}}
    return GitProcessor(extra_cmds=extra), Profiler()


def test_process_error(setup):
    handle, _ = setup

    with pytest.raises(ValueError):
        handle._generate_help_by_key("aa")


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git log --online --graph",
        "git log --dep 10 --online --graph",
        "git log --dep 10 --online --graph --color true",
        "git add xxx/xxx",
        "git checkout -b test",
    ],
)
def test_color_command(setup, command: str):
    handle, profiler = setup

    with profiler:
        color_str = handle.color_command(command)
        # print(repr(color_str))
        print(color_str)
        assert Fx.pure(color_str).strip() == command.strip()
    profiler.print()
