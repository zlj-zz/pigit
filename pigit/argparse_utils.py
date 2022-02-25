from typing import Union
from copy import deepcopy
from argparse import ArgumentParser, Namespace


class Parser(object):
    def __init__(self, args_dict: dict) -> None:
        self._args_dict = deepcopy(args_dict)

        self._parse_dict()

    def _parse_dict(self):
        """Parse `self._args_dict` to genrate a `ArgumentParser`."""

        def _parse_args(handle: ArgumentParser, args: dict):
            sub_parsers = None

            for name, prop in args.items():

                if name == "-groups":
                    # TODO: '_ArgumentGroup' object has no attribute 'add_subparsers'
                    for g_name, group in prop.items():
                        group_handle = handle.add_argument_group(
                            title=group.get("title", ""),
                            description=group.get("description", ""),
                        )
                        group_args: dict = group.get("args", {})

                        _parse_args(group_handle, group_args)

                elif "args" in prop:
                    # Cannot have multiple subparser arguments.
                    if not sub_parsers:
                        sub_parsers = handle.add_subparsers()

                    # Deleting `prop["args"]` dose not affect `sub_args`.
                    sub_args: dict = prop.get("args", None)
                    del prop["args"]

                    # Create subparser.
                    sub_handle: ArgumentParser = sub_parsers.add_parser(name, **prop)

                    # If `set_defaults` in args, special treatment is required.
                    set_defaults: dict = sub_args.get("set_defaults", None)
                    if set_defaults:
                        del sub_args["set_defaults"]
                        sub_handle.set_defaults(**set_defaults)

                    _parse_args(sub_handle, sub_args)

                else:
                    names: list[str] = name.split(" ")
                    handle.add_argument(*names, **prop)

        d = self._args_dict
        args: dict = d.get("args", {})

        # Create root parser.
        p = self._parser = ArgumentParser(
            prog=d.get("prog", None),
            prefix_chars=d.get("prefix_chars", None),
            description=d.get("description", None),
            add_help=d.get("add_help", True),
        )

        _parse_args(p, args)

    def parse(self, args: Union[list, str, None] = None) -> tuple[Namespace, list]:
        if not args:
            known_args, unknown = self._parser.parse_known_args()
        elif isinstance(args, list):
            known_args, unknown = self._parser.parse_known_args(args)
        elif isinstance(args, str):
            known_args, unknown = self._parser.parse_known_args(args.split())
        else:
            raise AttributeError("custom_commands need be list, str or empty.")

        return known_args, unknown


if __name__ == "__main__":
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
            "-groups": {
                "tools": {
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
                }
            },
            "cmd": {
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
    parser._parser.print_help()
    print(parser.parse())
