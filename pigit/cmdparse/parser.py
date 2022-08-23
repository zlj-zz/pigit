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
    Tuple,
    Union,
    overload,
)
from argparse import (
    Namespace,
    ArgumentParser,
    HelpFormatter,
    _SubParsersAction,
)
from shutil import get_terminal_size
from plenty.style import Style


if TYPE_CHECKING:
    from argparse import Action, FileType, _ArgumentGroup

FormatterStyle = Union[Style, str, None]


class ColorHelpFormatter(HelpFormatter):
    """Formatter for generating usage messages and argument help strings.
    This class inherits `argparse.HelpFormatter` and rewrites some methods
    to complete customization.
    """

    usage_style: FormatterStyle = "bold"
    text_style: FormatterStyle = "i sky_blue"
    command_style: FormatterStyle = "ok"
    help_style: FormatterStyle = "i yellow"

    def __init__(
        self,
        prog: str,
        indent_increment: int = 2,
        max_help_position: int = 24,
        width: Optional[int] = None,
    ):
        max_width, _ = get_terminal_size()
        if width is None:
            width = max_width * 2 // 3
        else:
            width = width if width < max_width else max_width - 2

        super().__init__(prog, indent_increment, max_help_position, width)

    def _format_usage(
        self,
        usage: str,
        actions: Iterable["Action"],
        groups: Iterable["_ArgumentGroup"],
        prefix: Optional[str],
    ) -> str:
        return Style.parse(self.usage_style).render(
            super()._format_usage(usage, actions, groups, prefix)
        )

    def _format_text(self, text: str) -> str:
        return Style.parse(self.text_style).render(super()._format_text(text))

    def _format_action(self, action: "Action") -> str:
        # determine the required width and the entry label
        help_position = min(self._action_max_length + 2, self._max_help_position)
        help_width = max(self._width - help_position, 11)
        action_width = help_position - self._current_indent - 2
        action_header = self._format_action_invocation(action)

        # no help; start on same line and add a final newline
        if not action.help:
            tup = self._current_indent, "", action_header
            action_header = "%*s%s\n" % tup

        # short action name; start on the same line and pad two spaces
        elif len(action_header) <= action_width:
            tup = self._current_indent, "", action_width, action_header
            action_header = "%*s%-*s  " % tup
            indent_first = 0

        # long action name; start on the next line
        else:
            tup = self._current_indent, "", action_header
            action_header = "%*s%s\n" % tup
            indent_first = help_position

        # collect the pieces of the action help
        # @Overwrite
        parts = [Style.parse(self.command_style).render(action_header)]

        # if there was help for the action, add lines of help text
        if action.help:
            help_text = self._expand_help(action)
            help_lines = self._split_lines(help_text, help_width)
            help_parts = ["%*s%s\n" % (indent_first, "", help_lines[0])]
            help_parts.extend(
                "%*s%s\n" % (help_position, "", line) for line in help_lines[1:]
            )
            parts.append(
                Style.parse(self.help_style).render(self._join_parts(help_parts))
            )

        elif not action_header.endswith("\n"):
            parts.append("\n")

        # if there are any sub-actions, add their help as well
        parts.extend(
            self._format_action(subaction)
            for subaction in self._iter_indented_subactions(action)
        )

        # return a single string
        return self._join_parts(parts)


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
        formatter_class: Sequence[HelpFormatter] = ColorHelpFormatter,
        prefix_chars: str = "-",
        fromfile_prefix_chars: Optional[str] = None,
        argument_default: Any = None,
        conflict_handler: str = "error",
        add_help: bool = True,
        allow_abbrev: bool = True,
        # exit_on_error: bool = True,  # python3.9 feature
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
    def from_dict(cls, parser_dict: Dict) -> "Parser":
        """Parse a `dict` to genrate a ~Parser."""
        from copy import deepcopy

        # Use `deepcopy` to ensure that the original dict will not be changed.
        parser_dict = deepcopy(parser_dict)

        def add_command(
            handle: Union["Parser", "_ArgumentGroup"],
            name: str,
            args: Dict[str, Any],
        ) -> None:
            """Add command to ~Parser or ~Group object."""

            names: List[str] = name.split(" ")
            handle.add_argument(*names, **args)

        def parse_args(handle: "Parser", args: Dict) -> None:
            sub_parsers: Optional["Parser"] = None

            for name, prop in args.items():
                # Get command type.
                prop_type = prop.pop("type", "")

                # If the type is 'groups', it's mean that need create a new custom
                # group. The command of the group in 'args', so we should iterative
                # the 'args' to add each command.
                if prop_type == "groups":
                    g_handle: "_ArgumentGroup" = handle.add_argument_group(
                        title=prop.get("title", ""),
                        description=prop.get("description", ""),
                    )
                    for g_name, g_prop in prop.get("args", {}).items():
                        add_command(g_handle, g_name, g_prop)

                # If the type is 'sub', is's mean that need create a new sub-parser.
                # Before create sub-parse, we need create a subparsers which a sub-parser
                # group. Be careful that cannot have multiple subparser arguments for same
                # ~ArgumentParser. The command of sub-parser in 'args' and it may include
                # smaller sub-parser, so should resolve it recursively.
                elif prop_type == "sub":
                    #
                    if not sub_parsers:
                        sub_parsers = handle.add_subparsers()

                    sub_args: Dict = prop.pop("args", None)

                    sub_handle: Sequence["Parser"] = sub_parsers.add_parser(
                        name, **prop
                    )

                    # If `set_defaults` in args, special treatment is required.
                    set_defaults: Dict = sub_args.get("set_defaults", None)
                    if set_defaults:
                        del sub_args["set_defaults"]
                        sub_handle.set_defaults(**set_defaults)

                    parse_args(sub_handle, sub_args)

                # Other types will be ignored, and it is considered that the current is
                # just an ordinary command to add.
                else:
                    add_command(handle, name, prop)

        args: Dict = parser_dict.pop("args", {})

        # Create root parser. Parse and add command.
        root_parser = cls(**parser_dict)
        parse_args(root_parser, args)

        return root_parser

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
            # Set parser parameters.
            for name in cmd_names:
                target_dict[name] = getattr(parser, name, None)

            # Init `args`.
            target_dict["args"] = args = {}

            # Iterative action groups. Include 'option', 'position' and 'subparsers'.
            # If define custom group, also include them.
            for action_group in parser._action_groups:
                # Iterative action in the group. The each action is adding by `add_argument`,
                # so one action is one argument. It include the parameters that we needed,
                # the name is define in `argument_names`. The only special type is
                # ～_SubParserAction, which is a sub-parser. We need to deal with it
                # separately and resolve its action groups recursively.
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
    metavar: Union[str, Tuple[str, ...], None] = None,
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
