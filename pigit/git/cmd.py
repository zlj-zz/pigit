# -*- coding:utf-8 -*-

from typing import Callable, Dict, List, Optional, Tuple, Union
import os
import re
import random
import textwrap
import logging

from ..common.utils import exec_cmd, confirm, similar_command, traceback_info
from ._cmds import GIT_CMDS, CommandType

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
            # load a module form location.
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


class SCmd:
    """Git short command handler."""

    def __init__(
        self,
        extra_cmds: Optional[dict] = None,
        command_prompt: bool = True,
        show_original: bool = True,
    ) -> None:
        self.prompt = command_prompt
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

        Returns:
            Tuple[int, str]: (code, msg)
                code:
                    0: successful
                    1: not supported
                    2: has no cmd string
                    3: func cmd exec error
                    5: not supported cmd type
        """

        msgs = []

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
            msgs.append(
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
                msgs.append(f":rainbow:  {self.color_command(command)}")
            exec_cmd(command, reply=False)
        else:
            return 5, "`The type of command not supported.`<error>"

        return 0, "\n".join(msgs)

    def do(self, short_cmd: str, args: Optional[Union[List, Tuple]] = None) -> str:
        """Process command and arguments."""

        code, msg = self.process_command(short_cmd, args)

        if code == 1 and self.prompt:  # check config.
            predicted_command = similar_command(short_cmd, self.cmds.keys())
            if confirm(f":TIPS: The wanted command is `{predicted_command}`?[y/n]:"):
                return self.do(predicted_command, args=args)

        return msg

    # ============================
    # Print command help message.
    # ============================
    def generate_help_by_key(
        self, key: str, use_color: bool = True, max_width: int = 90
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
        _help: str = self.cmds[key].get("help", "").strip()
        if _help:
            _help = textwrap.wrap(_help, msg_max_width)
            help_msg = _help[0] + "\n"
            for line in _help[1:]:
                help_msg += "%*s%s\n" % (help_position, "", line)
        else:
            help_msg = ""

        _command = self.cmds[key].get("command", "ERROR: empty command.")
        if callable(_command):
            _command = f"Func: {_command.__name__}"

        command_msg = "%*s%s" % (help_position, "", _command) if help_msg else _command

        if use_color:
            return f"  `{key:<13}`<ok>{help_msg}`{command_msg}`<gold>"
        else:
            return f"  {key:<12} {_help}{command_msg}"

    def get_help(self) -> str:
        """Get all help message."""

        msgs = ["These are short commands that can replace git operations:"]

        for key in self.cmds.keys():
            msg = self.generate_help_by_key(key)
            msgs.append(msg)

        return "\n".join(msgs)

    def print_help_by_type(self, t: str) -> str:
        """Print a part of help message.

        Print the help information of the corresponding part according to the
        incoming command type string. If there is no print error prompt for the
        type.

        Args:
            command_type (str): A command type of `TYPE`.
        """

        # Process received type.
        t = t.capitalize().strip()

        # Checking the type whether right.
        if t not in CommandType.__members__:
            predicted_type = similar_command(t, CommandType.__members__.keys())
            if self.prompt and confirm(
                f":TIPS: The wanted type is `{predicted_type}`?[y/n]:"
            ):
                return self.print_help_by_type(predicted_type)

            else:
                return (
                    "`There is no such type.`<error>\n"
                    "Please use `--types`<ok> to view the supported types."
                )

        # Get help.
        msgs = ["These are the orders of {0}".format(t)]

        for k, v in self.cmds.items():
            belong = v.get("belong", CommandType.Extra)
            # Prevent the `belong` attribute from being set in the custom command.
            if isinstance(belong, CommandType) and belong.value == t:
                msg = self.generate_help_by_key(k)
                msgs.append(msg)

        return "\n".join(msgs)

    @classmethod
    def get_types(cls) -> str:
        """Print all command types with random color."""
        msgs = []

        for member in CommandType:
            color_str = "#{:02X}{:02X}{:02X}".format(
                random.randint(70, 255),
                random.randint(70, 255),
                random.randint(70, 255),
            )

            msgs.append(f"`{member.value}`<{color_str}>")

        return " ".join(msgs)
