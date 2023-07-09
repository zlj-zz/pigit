# -*- coding:utf-8 -*-

from typing import Callable, Dict, List, Optional, Tuple, Union
import os, re, textwrap, random, logging

from plenty import get_console
from plenty.str_utils import shorten

from ..common.utils import exec_cmd, confirm, similar_command, traceback_info
from ..common.singleton import Singleton
from .shortcmds import GIT_CMDS, CommandType

Log = logging.getLogger(__name__)


def get_extra_cmds(name: str, path: str) -> Dict:
    """Get custom cmds.

    Load the `extra_cmds.py` file under PIGIT HOME, check whether `extra_cmds`
    exists, and return it. If not have, return a empty dict.

    Returns:
        (dict[str,str]): extra cmds dict.
    """
    import importlib.util

    extra_cmds = {}

    if os.path.isfile(path):
        try:
            # load a module form localtion.
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            Log.error(traceback_info(f"Can't load file '{path}'."))
        else:
            try:
                extra_cmds = module.extra_cmds  # type: ignore
            except AttributeError:
                Log.error("Can't found dict name is 'extra_cmds'.")

    return extra_cmds


class ShortGitter(metaclass=Singleton):
    """Git short command processor."""

    def __init__(
        self,
        extra_cmds: Optional[dict] = None,
        command_prompt: bool = True,
        show_original: bool = True,
        **kwargs,
    ) -> None:

        self.use_recommend = command_prompt
        self.show_original = show_original

        # Init commands.
        self.cmds = GIT_CMDS
        if extra_cmds:
            if not isinstance(extra_cmds, dict):
                raise TypeError("Custom cmds must be a dict.") from None
            self.cmds.update(extra_cmds)

    @staticmethod
    def color_command(command: str) -> str:
        """Return the command string with color.
        prog      : green;
        command   : yellow;
        arguments : skyblue;
        values    : white.
        """

        handle = re.match(r"(\w+)\s+(\w+)", command)
        prop = handle[1]
        cmd = handle[2]
        next_position = handle.span()[1]

        color_command = f"b`{prop}`<ok> b`{cmd}`<goldenrod> "

        arguments = re.findall(
            r"\s+(-?-?[^\s]+)(=?([\w-]+:)?(\".*?\"|\'.*?\'))?", command[next_position:]
        )
        for arg_handle, value, _, _ in arguments:
            color_command += f"`{arg_handle}`<sky_blue>{value} "

        return color_command

    def process_command(
        self, command_string: str, args: Optional[Union[List, Tuple]] = None
    ) -> Tuple[int, str]:
        """Process command and arguments.

        Args:
            command_ (str): short command string
            args (list|None, optional): command arguments. Defaults to None.
        """

        option: Optional[Dict[str, Dict]] = self.cmds.get(command_string, None)

        # Invalid, if need suggest.
        if option is None:
            return (
                1,
                f"Don't support this command: `{command_string}`<error>, "
                "please try `--show-commands`<gold>",
            )

        command: Optional[Union[str, Callable]] = option.get("command")
        # Has no command can be executed.
        if not command:
            return 2, "`Invalid custom short command, nothing can to exec.`<error>"

        if not option.get("has_arguments", False) and args:
            get_console().echo(
                f"`The command does not accept parameters. Discard {args}.`<error>"
            )
            args = []

        if isinstance(command, Callable):
            try:
                command(args)
            except Exception as e:
                return 3, f"`{e}`<error>"
        elif isinstance(command, str):
            if args:
                command = " ".join([command, *args])
            if self.show_original:
                get_console().echo(f":rainbow:  {self.color_command(command)}")
            exec_cmd(command, reply=False)
        else:
            return 5, "`The type of command not supported.`<error>"

        return 0, ""

    def do(self, command_string: str, args: Optional[Union[List, Tuple]] = None):
        """Process command and arguments."""

        code, msg = self.process_command(command_string, args)
        if code == 0:
            pass
        elif code == 1 and self.use_recommend:  # check config.
            predicted_command = similar_command(command_string, self.cmds.keys())
            if confirm(
                get_console().render_str(
                    f":thinking: The wanted command is `{predicted_command}`<ok> ?[y/n]:"
                )
            ):
                self.do(predicted_command, args=args)
        else:
            get_console().echo(msg)

    # ============================
    # Print command help message.
    # ============================
    def _generate_help_by_key(
        self, _key: str, use_color: bool = True, max_width=90
    ) -> str:
        """Generate one help by given key.

        Args:
            _key (str): Short command string.
            use_color (bool, optional): Whether color help message. Defaults to True.

        Returns:
            (str): Help message of one command.
        """

        help_position = 15
        msg_max_width = max_width - help_position

        # Get help message and command.
        _help: str = self.cmds[_key].get("help", "").strip()
        if _help:
            _help = textwrap.wrap(_help, msg_max_width)
            help_msg = _help[0] + "\n"
            for line in _help[1:]:
                help_msg += "%*s%s\n" % (help_position, "", line)
        else:
            help_msg = ""

        _command = self.cmds[_key].get("command", "ERROR: empty command.")
        if callable(_command):
            _command = f"Func: {_command.__name__}"

        _command = shorten(_command, msg_max_width, placeholder="...")
        command_msg = "%*s%s" % (help_position, "", _command) if help_msg else _command

        if use_color:
            return f"  `{_key:<13}`<ok>{help_msg}`{command_msg}`<gold>"
        else:
            return f"  {_key:<12} {_help}{command_msg}"

    def print_help(self) -> None:
        """Print help message."""
        print("These are short commands that can replace git operations:")
        for key in self.cmds.keys():
            msg = self._generate_help_by_key(key)
            get_console().echo(msg)

    def print_help_by_type(self, command_type: str) -> None:
        """Print a part of help message.

        Print the help information of the corresponding part according to the
        incoming command type string. If there is no print error prompt for the
        type.

        Args:
            command_type (str): A command type of `TYPE`.
        """

        # Process received type.
        command_type = command_type.capitalize().strip()

        # Checking the type whether right.
        if command_type not in CommandType.__members__:
            get_console().echo(
                "`There is no such type.`<error>\n"
                "Please use `git --types`<ok> to view the supported types."
            )

            if self.use_recommend:
                predicted_type = similar_command(
                    command_type, CommandType.__members__.keys()
                )
                if confirm(
                    get_console().render_str(
                        f":thinking: The wanted type is `{predicted_type}`<ok> ?[y/n]:"
                    )
                ):
                    self.print_help_by_type(predicted_type)
            return None

        # Print help.
        print("These are the orders of {0}".format(command_type))
        for k, v in self.cmds.items():
            belong = v.get("belong", CommandType.Extra)
            # Prevent the `belong` attribute from being set in the custom command.
            if isinstance(belong, CommandType) and belong.value == command_type:
                msg = self._generate_help_by_key(k)
                get_console().echo(msg)

    @classmethod
    def print_types(cls) -> None:
        """Print all command types with random color."""
        res = []

        for member in CommandType:
            color_str = "#{:02X}{:02X}{:02X}".format(
                random.randint(70, 255),
                random.randint(70, 255),
                random.randint(70, 255),
            )

            res.append(f"`{member.value}`<{color_str}>")

        get_console().echo(" ".join(res))
