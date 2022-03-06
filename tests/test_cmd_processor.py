import pytest
from .utils import analyze_it

from pigit.processor import CmdProcessor
from pigit.render import Fx


def test_init():
    with pytest.raises(TypeError):
        CmdProcessor(extra_cmds="xxx")


@pytest.fixture(scope="module")
def setup():
    extra = {"aa": {"help": "print system user name."}}
    return CmdProcessor(extra_cmds=extra)


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git add xxx/xxx",
        "git checkout -b test",
        "git log --online --graph",
        "git log --dep 10 --online --graph",
        "git log --dep 10 --online --graph --color true",
        'git log --topo-order --stat --pretty=format:"%C(bold yellow)commit"',
    ],
)
def test_color_command(setup, command: str):
    handle = setup

    color_str = handle.color_command(command)
    # print(repr(color_str))
    print(color_str)
    # assert Fx.pure(color_str).strip() == command.strip()
