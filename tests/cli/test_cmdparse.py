import pytest
import os
import copy
from pprint import pprint

from paths import PROJECT_ROOT as _PIGIT_PATH
from utils import analyze_it

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
            "help": "git short command system.",
            "description": "Execute short git commands.",
            "args": {
                "command": {
                    "nargs": "*",
                    "help": "Command to execute with arguments.",
                },
                "-l --list": {
                    "action": "store_true",
                    "help": "List all commands.",
                },
                "-d --dangerous": {
                    "action": "store_true",
                    "help": "List only dangerous commands.",
                },
                "-s --search": {
                    "dest": "search",
                    "metavar": "QUERY",
                    "help": "Search commands by keyword.",
                },
                "-p --pick": {
                    "dest": "pick",
                    "metavar": "CATEGORY",
                    "nargs": "?",
                    "const": True,
                    "help": "Interactively pick and run a command (TTY). Optional CATEGORY to filter.",
                },
                "-t --type": {
                    "dest": "type",
                    "metavar": "CATEGORY",
                    "help": "Filter by category (branch, commit, index, etc.).",
                },
                "set_defaults": {"func": range},
            },
        },
    },
}


def _inject_registry_commands(complete_vars):
    """Inject cmd_new registry commands into cmd completion, mirroring entry.py."""
    from pigit.git.cmds import get_registry, register_user_commands
    from pigit.cmdparse.completion.base import CompletionType

    register_user_commands()
    registry = get_registry()

    for cmd_def in registry.get_all():
        meta = cmd_def.meta
        if meta.arg_completion is None:
            arg_comp_value = ""
        elif isinstance(meta.arg_completion, list):
            arg_comp_value = meta.arg_completion[0].value if meta.arg_completion else ""
        else:
            arg_comp_value = meta.arg_completion.value

        cmd_entry = {
            "help": meta.help,
            "args": {},
            "arg_completion": arg_comp_value,
        }
        complete_vars["args"]["cmd"]["args"][meta.short] = cmd_entry

    for alias_name, target in registry.get_aliases().items():
        cmd_entry = {
            "help": f"Alias for {target}",
            "args": {},
            "arg_completion": "",
        }
        complete_vars["args"]["cmd"]["args"][alias_name] = cmd_entry


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
            _inject_registry_commands(cls.complete_vars)
        else:
            cls.complete_vars = copy.deepcopy(argparse_dict)

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
