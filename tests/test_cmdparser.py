import pytest, os, copy
from pprint import pprint
from .utils import analyze_it
from .conftest import _PIGIT_PATH

from pigit.cmdparse.parser import command, Parser
from pigit.cmdparse.shellcompletion.base import ShellCompletion
from pigit.cmdparse.shellcompletion import (
    ZshCompletion,
    BashCompletion,
    FishCompletion,
    shell_complete,
    get_shell,
)
from pigit.gitlib.shortcmds import GIT_CMDS

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

    ShellCompletion._SHELL = ""
    ShellCompletion._INJECT_PATH = ""
    args = parser.to_dict()["args"]
    pprint(ShellCompletion("", {})._parse(args))


class TestCompletion:
    real = True
    prog = "pigit"
    script_dir = os.path.join(_PIGIT_PATH, "docs")

    if real:
        from pigit.entry import pigit

        complete_vars = pigit.to_dict()
        complete_vars["args"]["cmd"]["args"].update(
            {k: {"help": v["help"], "args": {}} for k, v in GIT_CMDS.items()}
        )
    else:
        complete_vars = copy.deepcopy(argparse_dict)
        cmd_temp = complete_vars["args"]["cmd"]["args"]
        cmd_temp.update(
            {k: {"help": v["help"], "args": {}} for k, v in GIT_CMDS.items()}
        )

    def test_error_complete_vars(self):
        with pytest.raises(TypeError):
            BashCompletion("test", "xxx", ".")

    def print(self, c):
        print(c.prog_name)
        print(c.script_name)
        print(c.inject_path)

        source = c.generate_resource()
        print(source)

        c.write_completion(source)

    @analyze_it
    def test_bash(self):
        c = BashCompletion(None, self.complete_vars, self.script_dir)
        self.print(c)

    @analyze_it
    def test_zsh(self):
        c = ZshCompletion("pigit-dev", self.complete_vars, self.script_dir)
        self.print(c)

    def test_fish(self):
        c = FishCompletion(self.prog, self.complete_vars, self.script_dir)
        self.print(c)

    def test_get_shell(self):
        print(get_shell())

    def test_action(self):
        shell_complete(self.complete_vars, "bash", "xxx", ".", None, "./test.txt")
