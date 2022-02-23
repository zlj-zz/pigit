import argparse
from typing import Union


class Parser(object):
    def __init__(self, args_dict: dict) -> None:
        self._args_dict = args_dict

        self._parse_dict()

    def _parse_dict(self):
        d = self._args_dict
        p = self._parser = argparse.ArgumentParser(
            prog=d.get("prog", None),
            prefix_chars=d.get("prefix_chars", None),
            description=d.get("description", None),
            add_help=d.get("add_help", True),
        )

        def _parse_args(handle: argparse.ArgumentParser, args: dict):
            sub_parsers = None

            for name, prop in args.items():
                sub_args: dict = prop.get("args", None)

                if name == "-groups":
                    # TODO: '_ArgumentGroup' object has no attribute 'add_subparsers'
                    for g_name, group in prop.items():
                        group_handle = handle.add_argument_group(
                            title=group.get("title", ""),
                            description=group.get("description", ""),
                        )
                        group_args = group.get("args", {})

                        _parse_args(group_handle, group_args)

                elif not sub_args:
                    names: str = name.split(" ")
                    handle.add_argument(*names, **prop)

                else:
                    # Deleting `prop["args"]` dose not affect `sub_args`.
                    del prop["args"]

                    # cannot have multiple subparser arguments.
                    if not sub_parsers:
                        sub_parsers = handle.add_subparsers()

                    sub_handle: argparse.ArgumentParser = sub_parsers.add_parser(
                        name, **prop
                    )
                    set_defaults: dict = sub_args.get("set_defaults", None)
                    if set_defaults:
                        del sub_args["set_defaults"]
                        sub_handle.set_defaults(**set_defaults)

                    _parse_args(sub_handle, sub_args)

        args: dict = d.get("args", {})
        _parse_args(p, args)

    def parse(
        self, custom_commands: Union[list, str, None] = None
    ) -> tuple[argparse.Namespace, list]:
        if custom_commands:
            if isinstance(custom_commands, list):
                args, unknown = self._parser.parse_known_args(custom_commands)
            elif isinstance(custom_commands, str):
                args, unknown = self._parser.parse_known_args(custom_commands.split())
            else:
                raise AttributeError("custom_commands need be list or str.")
        else:
            args, unknown = self._parser.parse_known_args()

        return args, unknown


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
