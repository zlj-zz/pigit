# -*- coding:utf-8 -*-

import os
import re
import textwrap
import random
import logging
from typing import Dict, List, Optional, Tuple, Union

from ..common.utils import run_cmd, confirm, similar_command, traceback_info
from ..common.singleton import Singleton
from ..render import get_console
from ..render.str_utils import shorten
from .cmds import Git_Cmds, CommandType

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


class CmdProcessor(object, metaclass=Singleton):
    """Git short command processor."""

    def __init__(
        self,
        extra_cmds: Optional[dict] = None,
        command_prompt: bool = True,
        show_original: bool = True,
        **kwargs,
    ) -> None:
        super(CmdProcessor, self).__init__()

        self.use_recommend = command_prompt
        self.show_original = show_original

        self.cmds = Git_Cmds
        if extra_cmds:
            if not isinstance(extra_cmds, dict):
                raise TypeError("Custom cmds must be dict.")
            self.cmds.update(extra_cmds)

    @staticmethod
    def color_command(command: str) -> str:
        """Color the command string.
        prog: green;
        short command: yellow;
        arguments: skyblue;
        values: white.

        Args:
            command(str): valid command string.

        Returns:
            (str): color command string.
        """

        handle = re.match(r"(\w+)\s+(\w+)", command)
        prop = handle.group(1)
        cmd = handle.group(2)
        next_position = handle.span()[1]

        color_command = f"b`{prop}`<ok> b`{cmd}`<goldenrod> "

        arguments = re.findall(
            r"\s+(-?-?[^\s]+)(=?([\w-]+:)?(\".*?\"|\'.*?\'))?", command[next_position:]
        )
        for arg_handle, value, _, _ in arguments:
            color_command += f"`{arg_handle}`<sky_blue>{value} "

        return color_command

    def process_command(
        self, command_: str, args: Optional[Union[List, Tuple]] = None
    ) -> None:
        """Process command and arguments.

        Args:
            command_ (str): short command string
            args (list|None, optional): command arguments. Defaults to None.

        Raises:
            SystemExit: not git.
            SystemExit: short command not right.
        """

        option: Optional[Dict] = self.cmds.get(command_, None)

        # Invalid, if need suggest.
        if option is None:
            get_console().echo(
                "Don't support this command, please try `g --show-commands`<gold>"
            )

            if self.use_recommend:  # check config.
                predicted_command = similar_command(command_, self.cmds.keys())
                if confirm(
                    get_console().render_str(
                        f":thinking: The wanted command is `{predicted_command}`<ok> ?[y/n]:"
                    )
                ):
                    self.process_command(predicted_command, args=args)

            return None

        command = option.get("command", None)
        # Has no command can be executed.
        if not command:
            get_console().echo(
                "`Invalid custom short command, nothing can to exec.`<error>"
            )
            return None

        if not option.get("has_arguments", False) and args:
            get_console().echo(
                f"`The command does not accept parameters. Discard {args}.`<error>"
            )
            args = []

        _type = option.get("type", "command")
        if _type == "func":
            try:
                command(args)
            except Exception as e:
                get_console().echo(f"`{e}`<error>")
        else:  # is command.
            if args:
                args_str = " ".join(args)
                command = " ".join([command, args_str])
            if self.show_original:
                get_console().echo(f":rainbow:  {self.color_command(command)}")
            run_cmd(command)

    ################################
    # Print command help message.
    ################################
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

    def command_help(self) -> None:
        """Print help message."""
        print("These are short commands that can replace git operations:")
        for key in self.cmds.keys():
            msg = self._generate_help_by_key(key)
            get_console().echo(msg)

    def command_help_by_type(self, command_type: str) -> None:
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
                    self.command_help_by_type(predicted_type)
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
    def type_help(cls) -> None:
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
