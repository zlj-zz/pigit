from pprint import pprint
import pytest

from pigit.argparse_utils import Parser
from pigit.shellcompletion.base import ShellCompletion


def test():
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
    parser = Parser(argparse_dict)
    parser.parse_handle.print_help()

    assert isinstance(parser.parse("cmd ws"), tuple)
    assert isinstance(parser.parse(["cmd", "ws"]), tuple)

    with pytest.raises(AttributeError):
        parser.parse({})

    # with pytest.raises(SystemExit):
    # print(parser.parse())
    ShellCompletion._SHELL = ""
    ShellCompletion._INJECT_PATH = ""
    pprint(ShellCompletion("", {})._parse(argparse_dict["args"]))
