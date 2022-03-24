# -*- coding:utf-8 -*-
import os
import pytest
from unittest.mock import patch

from .utils import analyze_it

from pigit.processor import CmdProcessor, get_extra_cmds
from pigit.processor.cmd_func import add, set_email_and_username, fetch_remote_branch


class TestCmdProcessor:
    def test_init_error(self):
        with pytest.raises(TypeError):
            CmdProcessor(extra_cmds="xxx")

    @pytest.fixture(scope="module")
    def setup(self):
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
    def test_color_command(self, setup, command: str):
        from pigit.render import get_console

        console = get_console()
        handle = setup

        color_str = handle.color_command(command)
        console.echo(color_str)


def test_load_cmds():
    name = "test_module"
    file = f"./{name}.py"
    with open(file, "w") as f:
        f.write("""extra_cmds = { 'A': 1 }""")

    d = get_extra_cmds(name, file)
    assert d["A"] == 1

    os.remove(file)


@patch("pigit.processor.cmd_func.run_cmd", return_value=None)
def test_add(_):
    add([])


@patch("pigit.processor.cmd_func.run_cmd", return_value=None)
def test_fetch_remote(_):
    fetch_remote_branch([])


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("--global",),
        ("global",),
        ("-g",),
    ],
)
@patch("builtins.input", return_value="abc@gmail.com")
@patch("pigit.processor.cmd_func.run_cmd", return_value=False)
def test_set_ua(_a, _b, args):
    set_email_and_username(args)
