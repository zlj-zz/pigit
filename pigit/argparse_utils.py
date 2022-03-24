# -*- coding:utf-8 -*-

from typing import Dict, List, Tuple, Union
from copy import deepcopy
from argparse import ArgumentParser, Namespace


class Parser(object):
    """~Parser can parse a valid dict to generate cmd arguments."""

    def __init__(self, args_dict: Dict) -> None:
        self._args_dict = deepcopy(args_dict)
        self._parse_handle = None

    def _generate_handle_from_args(self) -> None:
        """Parse `self._args_dict` to genrate a `ArgumentParser`."""

        def _parse_args(handle: ArgumentParser, args: Dict) -> None:
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
        p = self._parse_handle = ArgumentParser(
            prog=d.get("prog", None),
            prefix_chars=d.get("prefix_chars", None),
            description=d.get("description", None),
            add_help=d.get("add_help", True),
        )

        _parse_args(p, args)

    @property
    def parse_handle(self):
        """Return a handle, create it when not exist."""
        if self._parse_handle is None:
            self._generate_handle_from_args()

        return self._parse_handle

    def parse(self, args: Union[List, str, None] = None) -> Tuple[Namespace, List]:
        if args is None:
            known_args, unknown = self.parse_handle.parse_known_args()
        elif isinstance(args, list):
            known_args, unknown = self.parse_handle.parse_known_args(args)
        elif isinstance(args, str):
            known_args, unknown = self.parse_handle.parse_known_args(args.split())
        else:
            raise AttributeError("custom_commands need be list, str or empty.")

        return known_args, unknown
