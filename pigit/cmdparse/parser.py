from __future__ import annotations

from argparse import (
    ArgumentParser,
    HelpFormatter,
    Namespace,
    _SubParsersAction,
)
from shutil import get_terminal_size
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    TypedDict,
    overload,
)
from collections.abc import Callable, Iterable, Sequence

from ..termui.cli_output import styled

if TYPE_CHECKING:
    from argparse import Action, FileType, _ArgumentGroup


class ParserOptions(TypedDict, total=False):
    title: str | None
    description: str | None
    parser_class: Parser | None
    action: Action | None
    option_string: str | None
    dest: str | None
    required: bool
    help: str | None
    metavar: str | None


class ColorHelpFormatter(HelpFormatter):
    """Formatter for generating usage messages and argument help strings.
    This class inherits `argparse.HelpFormatter` and rewrites some methods
    to complete customization.
    """

    def __init__(
        self,
        prog: str,
        indent_increment: int = 2,
        max_help_position: int = 24,
        width: int | None = None,
    ):
        max_width, _ = get_terminal_size()
        if width is None:
            width = max_width * 2 // 3
        else:
            width = width if width < max_width else max_width - 2

        super().__init__(prog, indent_increment, max_help_position, width)

    def _format_usage(
        self,
        usage: str | None,
        actions: Iterable[Action],
        groups: Iterable,
        prefix: str | None,
    ) -> str:
        return styled(super()._format_usage(usage, actions, groups, prefix), bold=True)

    def _format_text(self, text: str) -> str:
        return styled(super()._format_text(text), fg="sky_blue", italic=True)

    def _format_action(self, action: Action) -> str:
        # determine the required width and the entry label
        help_position = min(self._action_max_length + 2, self._max_help_position)
        help_width = max(self._width - help_position, 11)
        action_width = help_position - self._current_indent - 2
        action_header = self._format_action_invocation(action)

        # no help; start on same line and add a final newline
        if not action.help:
            tup = self._current_indent, "", action_header
            action_header = "%*s%s\n" % tup
            indent_first = 0

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
        parts = [styled(action_header, fg="green")]

        # if there was help for the action, add lines of help text
        if action.help:
            help_text = self._expand_help(action)
            help_lines = self._split_lines(help_text, help_width)
            help_parts = ["%*s%s\n" % (indent_first, "", help_lines[0])]
            help_parts.extend(
                "%*s%s\n" % (help_position, "", line) for line in help_lines[1:]
            )
            parts.append(styled(self._join_parts(help_parts), fg="yellow", italic=True))

        elif not action_header.endswith("\n"):
            parts.append("\n")

        # if there are any sub-actions, add their help as well
        parts.extend(
            self._format_action(sub_action)
            for sub_action in self._iter_indented_subactions(action)
        )

        # return a single string
        return self._join_parts(parts)


class ParserError(Exception):
    """Error class of ~Parser."""


class Parser(ArgumentParser):
    def __init__(
        self,
        prog: str | None = None,
        usage: str | None = None,
        description: str | None = None,
        epilog: str | None = None,
        parents: Sequence[ArgumentParser] | None = None,
        formatter_class: type[HelpFormatter] = ColorHelpFormatter,
        prefix_chars: str = "-",
        fromfile_prefix_chars: str | None = None,
        argument_default: Any = None,
        conflict_handler: str = "error",
        add_help: bool = True,
        allow_abbrev: bool = True,
        callback: Callable | None = None,
        **kwargs,
    ) -> None:
        if parents is None:
            parents = []
        super().__init__(
            prog=prog,
            usage=usage,
            description=description,
            epilog=epilog,
            parents=parents,
            formatter_class=formatter_class,
            prefix_chars=prefix_chars,
            fromfile_prefix_chars=fromfile_prefix_chars,
            argument_default=argument_default,
            conflict_handler=conflict_handler,
            add_help=add_help,
            allow_abbrev=allow_abbrev,
            **kwargs,
        )

        self.subparsers_action: _SubParsersAction | None = None
        self.default_callback = callback

    # ================================
    # overload ~ArgumentParser method
    # ================================
    def add_subparsers(self, **kwargs) -> _SubParsersAction:
        # cannot have multiple subparser arguments
        if self.subparsers_action is None:
            self.subparsers_action = super().add_subparsers(**kwargs)
        return self.subparsers_action

    # ============
    # call method
    # ============
    def main(self, args: list[str] | None = None, **kwargs):
        known_args: Namespace
        unknown: list

        known_args, unknown = self.parse_known_args(args)
        # print("call", known_args, unknown)

        if "sub_callback" in known_args:
            known_args.sub_callback(known_args, unknown)
        elif self.default_callback is not None:
            self.default_callback(known_args, unknown)

    def __call__(self, args: list[str] | None = None, **kwds: Any) -> Any:
        self.main(args, **kwds)

    # ===============================
    # tools methods of serialization
    # ===============================
    @classmethod
    def from_dict(cls, parser_dict: dict) -> Parser:
        """Parse a `dict` to generate a ~Parser."""
        from copy import deepcopy

        # Use `deepcopy` to ensure that the original dict will not be changed.
        parser_dict = deepcopy(parser_dict)

        def add_command(
            handle: Parser | _ArgumentGroup,
            name: str,
            args: dict[str, Any],
        ) -> None:
            """Add command to ~Parser or ~Group object."""

            names: list[str] = name.split(" ")
            handle.add_argument(*names, **args)

        def parse_args(handle: Parser, args: dict) -> None:
            sub_parsers: _SubParsersAction | None = None

            for name, prop in args.items():
                # Get command type.
                prop_type = prop.pop("type", "")

                # If the type is 'groups', it's mean that need create a new custom
                # group. The command of the group in 'args', so we should iterative
                # the 'args' to add each command.
                if prop_type == "groups":
                    g_handle: _ArgumentGroup = handle.add_argument_group(
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

                    sub_args: dict = prop.pop("args", None)

                    sub_handle: Parser = sub_parsers.add_parser(name, **prop)

                    # If `set_defaults` in args, special treatment is required.
                    set_defaults = sub_args.get("set_defaults")
                    if set_defaults is not None:
                        del sub_args["set_defaults"]
                        sub_handle.set_defaults(**set_defaults)

                    parse_args(sub_handle, sub_args)

                # Other types will be ignored, and it is considered that the current is
                # just an ordinary command to add.
                else:
                    add_command(handle, name, prop)

        args: dict = parser_dict.pop("args", {})

        # Create root parser. Parse and add command.
        root_parser = cls(**parser_dict)
        parse_args(root_parser, args)

        return root_parser

    def to_dict(self) -> dict:
        """Return a dict of a parameter serialization of ~Parser."""

        cmd_names: list[str] = [
            "prog",
            "usage",
            "description",
            "epilog",
            "prefix_chars",
        ]
        argument_names: list[str] = [
            "nargs",
            "const",
            "dest",
            "default",
            "type",
            "metavar",
            "help",
        ]

        def _process(parser: Parser, target_dict: dict) -> dict:
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
                        arg_completion = getattr(action, "arg_completion", None)
                        if arg_completion is not None:
                            args[option_string]["arg_completion"] = arg_completion

            return target_dict

        return _process(self, {})

    # ===============================
    # quick add sub-parser decorator
    # ===============================
    @overload
    def sub_parser(
        self,
        prog: str,
        *,
        title: str | None = None,
        description: str | None = None,
        parser_class: Parser | None = None,
        action: Action | None = None,
        option_string: str | None = None,
        dest: str | None = None,
        required: bool = False,
        help: str | None = None,
        metavar: str | None = None,
    ) -> Callable[..., Parser]: ...

    @overload
    def sub_parser(self, prog: str, **kwargs) -> Callable[..., Parser]: ...

    def sub_parser(self, prog: str, **kwargs) -> Callable[..., Parser]:
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

        def decorator(fn: Callable[..., Any]) -> Parser:
            nonlocal kwargs
            attr_params = kwargs.pop("params", None)
            params = attr_params if attr_params is not None else []

            decorator_params = getattr(fn, "__parser_params__", None)
            if decorator_params is not None:
                delattr(fn, "__parser_params__")
                params.extend(decorator_params)

            if "description" not in kwargs:
                kwargs["description"] = fn.__doc__

            parser = self.add_subparsers().add_parser(prog, **kwargs)

            _apply_params(parser, params)

            parser.set_defaults(sub_callback=fn)

            return parser

        return decorator


# ====================================
# decorator method of creating parser
# ====================================
@overload
def command(
    prog: str | None = None,
    cls: type[Parser] | None = None,
    *,
    usage: str | None = None,
    description: str | None = None,
    epilog: str | None = None,
    parents: Sequence[Parser] | None = None,
    formatter_class: type[HelpFormatter] = HelpFormatter,
    prefix_chars: str = "-",
    fromfile_prefix_chars: str | None = None,
    argument_default: Any = None,
    conflict_handler: str = "error",
    add_help: bool = True,
    allow_abbrev: bool = True,
    exit_on_error: bool = True,
    callback: Callable | None = None,
) -> Callable[..., Parser]: ...


@overload
def command(
    prog: str | None = None,
    cls: type[Parser] | None = None,
    **attrs,
) -> Callable[..., Parser]: ...


def command(
    prog: str | None = None,
    cls: type[Parser] | None = None,
    **attrs,
) -> Callable[..., Parser]:
    """Creates a new ~Parser and uses the decorated function as callback.
    This will also automatically attach all decorated :func:`argument` as
    parameters to the parser.

    The name of the command defaults to the name of the function with
    underscores replaced by dashes. If you want to change that, you can
    pass the intended name as the first argument.
    """

    if cls is None:
        cls = Parser

    fn: Callable | None = None
    if callable(prog):
        fn = prog
        prog = None

    def decorator(fn: Callable[..., Any]) -> Parser:
        kwargs = attrs
        group_configs = kwargs.pop("groups", None)
        attr_params = kwargs.pop("params", None)
        params = attr_params if attr_params is not None else []

        decorator_params = getattr(fn, "__parser_params__", None)
        if decorator_params is not None:
            delattr(fn, "__parser_params__")
            params.extend(decorator_params)

        if "description" not in kwargs:
            kwargs["description"] = fn.__doc__

        cmd = cls(
            prog=prog or fn.__name__.lower().replace("_", "-").strip(),
            callback=fn,
            **kwargs,
        )

        _apply_params(cmd, params, group_configs=group_configs)

        return cmd

    return decorator(fn) if fn is not None else decorator


def _param_memo(fn: Callable[..., Any], params) -> None:
    if not hasattr(fn, "__parser_params__"):
        setattr(fn, "__parser_params__", [])

    getattr(fn, "__parser_params__").append(params)


def _apply_params(
    parser, params: list, *, group_configs: dict[str, dict] | None = None
) -> None:
    """Register arguments on a parser, creating argument groups as needed.

    Supports a ``group`` keyword in argument kwargs: arguments with the same
    ``group`` value are placed in a shared ``add_argument_group``.
    The ``group`` key is consumed and never passed to argparse.

    ``group_configs`` maps a group name to keyword arguments for
    ``add_argument_group`` (e.g. ``title`` and ``description``).
    """
    groups: dict[str, Any] = {}
    group_configs = group_configs or {}
    for arg_names, arg_kwargs in params:
        group_name = arg_kwargs.pop("group", None)
        arg_completion = arg_kwargs.pop("arg_completion", None)
        target = parser
        if group_name is not None:
            if group_name not in groups:
                config = group_configs.get(group_name, {})
                groups[group_name] = parser.add_argument_group(
                    title=config.get("title", group_name),
                    description=config.get("description"),
                )
            target = groups[group_name]
        action = target.add_argument(*arg_names, **arg_kwargs)
        if arg_completion is not None:
            action.arg_completion = arg_completion


@overload
def argument(
    name: str,
    *,
    action: (
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
        ]
        | Sequence[Action]
        | None
    ) = None,
    nargs: int | Literal["?", "*", "+", "...", "A...", "==SUPPRESS=="] | None = None,
    const: Any | None = None,
    default: Any | None = None,
    type: Callable | FileType | None = None,
    choices: Iterable | None = None,
    required: bool | None = None,
    help: str | None = None,
    metavar: str | tuple[str, ...] | None = None,
    dest: str | None = None,
    version: str | None = None,
    **kwargs: Any,
) -> Callable: ...


@overload
def argument(name: str, **kwargs) -> Callable: ...


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
        names: list[str] = name.strip().split()
        _param_memo(fn, (names, kwargs))

        return fn

    return decorator
