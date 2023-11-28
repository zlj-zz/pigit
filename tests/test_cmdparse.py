import pytest
import os
import copy
from pprint import pprint

from .conftest import _PIGIT_PATH
from .utils import analyze_it

from pigit.git._cmds import Git_Proxy_Cmds
from pigit.cmdparse.parser import command, Parser
from pigit.cmdparse.completion.base import ShellCompletion, ShellCompletionError
from pigit.cmdparse.completion import (
    ZshCompletion,
    BashCompletion,
    FishCompletion,
    shell_complete,
    get_shell,
)


argparse_dict = {
    "prog": "pigit",
    "prefix_chars": "-",
    "description": "Pigit TUI is called automatically if no parameters are followed.",
    "args": {
        "-v --version": {
            "action": "version",
            "help": "Show version and exit.",
            "version": "Version: ",
        },
        "-d --debug": {
            "action": "store_true",
            "help": "Current runtime in debug mode.",
        },
        "--out-log": {"action": "store_true", "help": "Print log to console."},
        "tools": {
            "type": "groups",
            "title": "tools arguments",
            "description": "Auxiliary type commands.",
            "args": {
                "-c --count": {
                    "nargs": "?",
                    "const": ".",
                    "type": str,
                    "metavar": "PATH",
                    "help": "Count the number of codes and output them in tabular form."
                    "A given path can be accepted, and the default is the current directory.",
                },
                "--create-config": {
                    "action": "store_true",
                    "help": "Create a pre-configured file of PIGIT."
                    "(If a profile exists, the values available in it are used)",
                },
            },
        },
        "cmd": {
            "type": "sub",
            "help": "git short command.",
            "description": "If you want to use some original git commands, please use -- to indicate.",
            "args": {
                "command": {
                    "nargs": "?",
                    "type": str,
                    "default": None,
                    "help": "Short git command or other.",
                },
                "args": {
                    "nargs": "*",
                    "type": str,
                    "help": "Command parameter list.",
                },
                "-t --types": {
                    "action": "store_true",
                    "help": "List all command types and exit.",
                },
                "set_defaults": {"func": range},
            },
        },
    },
}


def test_generate_about_dict():
    parser = Parser.from_dict(argparse_dict)
    parser.print_help()

    ShellCompletion.SHELL = ""
    args = parser.to_dict()["args"]
    pprint(ShellCompletion("", {})._parse(args))


class TestCompletion:
    @classmethod
    def setup_class(cls):
        real = True

        cls.prog = "pigit"
        cls.script_dir = os.path.join(_PIGIT_PATH, "docs")

        if real:
            from pigit.entry import pigit

            cls.complete_vars = pigit.to_dict()
            cls.complete_vars["args"]["cmd"]["args"].update(
                {k: {"help": v["help"], "args": {}} for k, v in Git_Proxy_Cmds.items()}
            )
        else:
            cls.complete_vars = copy.deepcopy(argparse_dict)
            cmd_temp = cls.complete_vars["args"]["cmd"]["args"]
            cmd_temp.update(
                {k: {"help": v["help"], "args": {}} for k, v in Git_Proxy_Cmds.items()}
            )

    def test_error(self):
        # error complete_vars
        with pytest.raises(TypeError):
            BashCompletion("test", "xxx", ".")

        # error prog
        with pytest.raises(ShellCompletionError):
            BashCompletion(None, {}, ".")

    def print(self, c: ShellCompletion):
        assert c.prog_name == "pigit"

        assert c.script_name == f"pigit_{c.SHELL}_comp"

        source = c.generate_resource()
        # print(source)

        c.write_completion(source)

    def test_bash(self):
        c = BashCompletion(None, self.complete_vars, self.script_dir)
        self.print(c)

    @analyze_it
    def test_zsh(self):
        c = ZshCompletion("pigit", self.complete_vars, self.script_dir)
        self.print(c)

    def test_fish(self):
        c = FishCompletion(self.prog, self.complete_vars, self.script_dir)
        self.print(c)

    def test_get_shell(self):
        assert get_shell() in ["bash", "zsh", "fish", ""]

    def test_action(self):
        shell_complete(self.complete_vars, "bash", "xxx", ".", "./test.txt")
