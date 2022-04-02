# -*- coding:utf-8 -*-

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Sequence,
    Union,
    overload,
)
from argparse import Namespace, ArgumentParser, HelpFormatter, _SubParsersAction


if TYPE_CHECKING:
    from argparse import Action, FileType, _ArgumentGroup


class ParserError(Exception):
    """Error class of ~Parser."""


class Parser(ArgumentParser):
    def __init__(
        self,
        prog: Optional[str] = None,
        usage: Optional[str] = None,
        description: Optional[str] = None,
        epilog: Optional[str] = None,
        parents: Sequence[ArgumentParser] = None,
        formatter_class: HelpFormatter = HelpFormatter,
        prefix_chars: str = "-",
        fromfile_prefix_chars: Optional[str] = None,
        argument_default: Any = None,
        conflict_handler: str = "error",
        add_help: bool = True,
        allow_abbrev: bool = True,
        exit_on_error: bool = True,
        callback: Optional[Callable] = None,
    ) -> None:
        if parents is None:
            parents = []
        super().__init__(
            prog,
            usage,
            description,
            epilog,
            parents,
            formatter_class,
            prefix_chars,
            fromfile_prefix_chars,
            argument_default,
            conflict_handler,
            add_help,
            allow_abbrev,
            exit_on_error,
        )

        self.subparsers_action: Optional["_SubParsersAction"] = None
        self.default_callback = callback

    # ================================
    # overload ~ArgumentParser method
    # ================================
    def add_subparsers(self, **kwargs):
        self.subparsers_action = super().add_subparsers(**kwargs)
        return self.subparsers_action

    # ============
    # call method
    # ============
    def main(self, args: Optional[List[str]] = None, **kwargs):
        known_args: Namespace
        unknown: List

        known_args, unknown = self.parse_known_args(args)
        # print("call", known_args, unknown)

        if "sub_callback" in known_args:
            known_args.sub_callback(known_args, unknown)
        elif self.default_callback is not None:
            self.default_callback(known_args, unknown)

    def __call__(self, args: Optional[List[str]] = None, **kwds: Any) -> Any:
        self.main(args, **kwds)

    # ===============================
    # tools methods of serialization
    # ===============================
    @classmethod
    def from_dict(cls, top_dict: Dict) -> "Parser":
        """Parse a `dict` to genrate a ~Parser."""
        from copy import deepcopy

        top_dict = deepcopy(top_dict)

        def add_command(
            handle: Union["Parser", "_ArgumentGroup"],
            name: str,
            args: Dict[str, Any],
        ) -> None:
            """Add command to handle object."""
            names: List[str] = name.split(" ")
            handle.add_argument(*names, **args)

        def parse_args(handle: "Parser", args: Dict) -> None:
            sub_parsers: Optional["Parser"] = None

            for name, prop in args.items():
                # Get command type.
                prop_type = prop.pop("type", "")

                # Process command according to type.
                if prop_type == "groups":
                    # Create argument group.
                    g_handle: "_ArgumentGroup" = handle.add_argument_group(
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
                    sub_args: Dict = prop.pop("args", None)

                    # Create subparser.
                    sub_handle: Sequence["Parser"] = sub_parsers.add_parser(
                        name, **prop
                    )

                    # If `set_defaults` in args, special treatment is required.
                    set_defaults: Dict = sub_args.get("set_defaults", None)
                    if set_defaults:
                        del sub_args["set_defaults"]
                        sub_handle.set_defaults(**set_defaults)

                    parse_args(sub_handle, sub_args)

                else:
                    add_command(handle, name, prop)

        args: dict = top_dict.pop("args", {})

        # Create root parser.
        p = cls(**top_dict)
        # Parse and add command.
        parse_args(p, args)

        return p

    def to_dict(self) -> Dict:
        """Return a dict of a parameter serialization of ~Parser."""

        cmd_names: List[str] = [
            "prog",
            "usage",
            "description",
            "epilog",
            "prefix_chars",
        ]
        argument_names: List[str] = [
            "nargs",
            "const",
            "dest",
            "default",
            "type",
            "metavar",
            "help",
        ]

        def _process(parser: Sequence["Parser"], target_dict: Dict) -> Dict:
            for name in cmd_names:
                target_dict[name] = getattr(parser, name, None)

            target_dict["args"] = args = {}

            for action_group in parser._action_groups:
                for action in action_group._group_actions:
                    if isinstance(action, _SubParsersAction):
                        sub_helps = {
                            choices_action.dest: choices_action.help
                            for choices_action in action._choices_actions
                        }
                        for sub_prog, sub_parser in action._name_parser_map.items():
                            args[sub_prog] = _process(sub_parser, {})
                            args[sub_prog]["help"] = sub_helps.get(sub_prog, "_")
                            args[sub_prog]["type"] = "sub"
                    else:
                        option_string = " ".join(action.option_strings)
                        args[option_string] = {}

                        for name in argument_names:
                            args[option_string][name] = getattr(action, name, None)

            return target_dict

        return _process(self, {})

    def complete_help(self) -> Dict:
        """Return a dict of command with help message."""

        def _process(parser: Sequence["Parser"]) -> Dict:
            prefix_chars = parser.prefix_chars
            _positions = []
            _options = []
            _subparsers = {}

            for action_group in parser._action_groups:
                for action in action_group._group_actions:
                    if isinstance(action, _SubParsersAction):
                        sub_helps = {
                            choices_action.dest: choices_action.help
                            for choices_action in action._choices_actions
                        }
                        for sub_prog, sub_parser in action._name_parser_map.items():
                            _subparsers[sub_prog] = _process(sub_parser)
                            _subparsers[sub_prog]["help"] = sub_helps.get(sub_prog, "_")
                    else:
                        for option_string in action.option_strings:
                            help_string = action.help.replace("\n", "")
                            if option_string[0] in prefix_chars:
                                _options.append((option_string, help_string))
                            else:
                                _positions.append((option_string, help_string))

            return {
                "_positions": _positions,
                "_options": _options,
                "_subparsers": _subparsers,
            }

        return _process(self)

    # ===============================
    # quick add sub-parser decorator
    # ===============================
    @overload
    def sub_parser(
        self,
        prog: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        parser_class: Optional["Parser"] = None,
        action: Optional["Action"] = None,
        option_string: Optional[str] = None,
        dest: Optional[str] = None,
        required: bool = False,
        help: Optional[str] = None,
        metavar: Optional[str] = None,
    ) -> "Parser":
        ...

    def sub_parser(self, prog: str, **kwargs) -> "Parser":
        """Create a new ~Parser of subparser and use the decorator use callback.
        This will also automatically attach all decorated :func:`argument` as
        parameters to the parser.

        Args:
            prog (str): the prog name of subparser.

        Raises:
            ParserError: when the prog is not str.

        Returns:
            Parser:
        """

        if not isinstance(prog, str):
            raise ParserError(
                f"The name of sub_parser must be str, but given a {type(prog).__name__}."
            ) from None

        if self.subparsers_action is None:
            self.add_subparsers()

        def decorator(fn: Callable[..., Any]) -> "Parser":
            nonlocal kwargs
            attr_params = kwargs.pop("params", None)
            params = attr_params if attr_params is not None else []

            try:
                decorator_params = fn.__parser_params__
            except AttributeError:
                pass
            else:
                del fn.__parser_params__
                params.extend(decorator_params)

            if "description" not in kwargs:
                kwargs["description"] = fn.__doc__

            parser = self.subparsers_action.add_parser(prog, **kwargs)
            for args, kwargs in params:
                parser.add_argument(*args, **kwargs)

            parser.set_defaults(sub_callback=fn)

            return parser

        return decorator


# ====================================
# decorator method of creating parser
# ====================================
@overload
def command(
    prog: Union[str, Callable, None] = None,
    cls: Sequence[Parser] = None,
    usage: Optional[str] = None,
    description: Optional[str] = None,
    epilog: Optional[str] = None,
    parents: Sequence[Parser] = None,
    formatter_class: HelpFormatter = HelpFormatter,
    prefix_chars: str = "-",
    fromfile_prefix_chars: Optional[str] = None,
    argument_default: Any = None,
    conflict_handler: str = "error",
    add_help: bool = True,
    allow_abbrev: bool = True,
    exit_on_error: bool = True,
    callback: Optional[Callable] = None,
) -> Parser:
    ...


def command(
    prog: Union[str, Callable, None] = None, cls: Sequence[Parser] = None, **attrs
) -> Parser:
    """Creates a new ~Parser and uses the decorated function as callback.
    This will also automatically attach all decorated :func:`argument` as
    parameters to the parser.

    The name of the command defaults to the name of the function with
    underscores replaced by dashes. If you want to change that, you can
    pass the intended name as the first argument.
    """

    if cls is None:
        cls = Parser

    fn: Optional[Callable] = None
    if callable(prog):
        fn = prog
        prog = None

    def decorator(fn: Callable[..., Any]) -> Parser:
        kwargs = attrs
        attr_params = kwargs.pop("params", None)
        params = attr_params if attr_params is not None else []

        try:
            decorator_params = fn.__parser_params__
        except AttributeError:
            pass
        else:
            del fn.__parser_params__
            params.extend(decorator_params)

        if "description" not in kwargs:
            kwargs["description"] = fn.__doc__

        cmd = cls(
            prog=prog or fn.__name__.lower().replace("_", "-").strip(),
            callback=fn,
            **kwargs,
        )

        for args, kwargs in params:
            cmd.add_argument(*args, **kwargs)

        return cmd

    if fn is not None:
        return decorator(fn)

    return decorator


def _param_memo(fn: Callable[..., Any], params) -> None:
    if not hasattr(fn, "__parser_params__"):
        fn.__parser_params__ = []

    fn.__parser_params__.append(params)


@overload
def argument(
    name: str,
    action: Union[
        Literal[
            "store",
            "store_const",
            "store_true",
            "store_false",
            "append",
            "append_const",
            "count",
            "help",
            "version",
            "extend",
        ],
        Sequence["Action"],
        None,
    ] = None,
    nargs: Union[
        int, Literal["?", "*", "+", "...", "A...", "==SUPPRESS=="], None
    ] = None,
    const: Optional[Any] = None,
    default: Optional[Any] = None,
    type: Union[Callable, "FileType", None] = None,
    choices: Optional[Iterable] = None,
    required: Optional[bool] = None,
    help: Optional[str] = None,
    metavar: Union[str, tuple[str, ...], None] = None,
    dest: Optional[str] = None,
    version: Optional[str] = None,
    **kwargs: Any,
) -> Callable:
    ...


def argument(name: str, **kwargs) -> Callable:
    """Attaches an argument to the parser, allow position or option."""

    if not isinstance(name, str):
        raise TypeError(
            f"The type of 'name' must be str, but receive {type(name).__name__}."
        ) from None

    def decorator(fn: Callable[..., Any]) -> Callable:
        if "help" not in kwargs:
            kwargs["help"] = fn.__doc__

        # Check each name whether valid.
        names: List[str] = name.strip().split()
        _param_memo(fn, (names, kwargs))

        return fn

    return decorator
