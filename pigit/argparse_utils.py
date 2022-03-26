# -*- coding:utf-8 -*-

from typing import Any, Dict, List, Tuple, Union
from argparse import ArgumentParser, Namespace, _ArgumentGroup
from copy import deepcopy


class Parser(object):
    """~Parser can parse a valid dict to generate cmd arguments.

    It is realized by encapsulating ~ArgumentParser. Some parameters
    can refer to ~ArgumentParser.

    Example:
        d = {
            "prog": prog name, like: 'pigit',
            "prefix_chars": default is `-`,
            "description": description message of the Parser,
            "args": {
                "command name": {
                    'type': ... [groups, sub, None],
                    ... command arguments,
                    "set_defaults": a dict, will use `set_defaults` method,
                },
                ...,
            },
        }
    """

    def __init__(self, args_dict: Dict) -> None:
        self._args_dict = deepcopy(args_dict)
        self._parse_handle = None

    def _parse_from_args(self) -> None:
        """Parse `self._args_dict` to genrate a `ArgumentParser`."""

        def add_command(
            handle: Union[ArgumentParser, _ArgumentGroup],
            name: str,
            args: Dict[str, Any],
        ) -> None:
            """Add command to handle object."""
            # print(name)
            names: list[str] = name.split(" ")
            handle.add_argument(*names, **args)

        def _parse_args(handle: ArgumentParser, args: Dict) -> None:
            sub_parsers: ArgumentParser = None

            for name, prop in args.items():
                # Get command type.
                prop_type = prop.get("type")
                if prop_type:
                    del prop["type"]

                # Process command according to type.
                if prop_type == "groups":
                    # Create argument group.
                    g_handle: _ArgumentGroup = handle.add_argument_group(
                        title=prop.get("title", ""),
                        description=prop.get("description", ""),
                    )
                    # Add command to group.
                    for g_name, g_prop in prop.get("args", {}).items():
                        add_command(g_handle, g_name, g_prop)

                elif prop_type == "sub":
                    # Cannot have multiple subparser arguments for same ~ArgumentParser.
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
                    add_command(handle, name, prop)

        top_dict = self._args_dict
        args: dict = top_dict.get("args", {})
        del top_dict["args"]

        # Create root parser.
        p = self._parse_handle = ArgumentParser(**top_dict)
        # Parse and add command.
        _parse_args(p, args)

    @property
    def parse_handle(self):
        """Return a handle, create it when not exist."""
        if self._parse_handle is None:
            self._parse_from_args()

        return self._parse_handle

    def parse(self, args: Union[List, str, None] = None) -> Tuple[Namespace, List]:
        """Parse argument."""

        if args is None:
            known_args, unknown = self.parse_handle.parse_known_args()
        elif isinstance(args, list):
            known_args, unknown = self.parse_handle.parse_known_args(args)
        elif isinstance(args, str):
            known_args, unknown = self.parse_handle.parse_known_args(args.split())
        else:
            raise AttributeError("custom_commands need be list, str or empty.")

        return known_args, unknown
