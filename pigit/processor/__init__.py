# -*- coding:utf-8 -*-

import random
from typing import Optional, Union

from ..common import (
    Fx,
    Color,
    Emoji,
    render_str,
    run_cmd,
    confirm,
    similar_command,
    shorten,
)
from .cmds import Git_Cmds, CommandType


class CmdProcessor(object):
    """Git short command processor."""

    def __init__(
        self,
        extra_cmds: Optional[dict] = None,
        use_recommend: bool = True,
        show_original: bool = True,
        **kwargs,
    ) -> None:
        super(CmdProcessor, self).__init__()

        self.use_recommend = use_recommend
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

        command_list = command.split(" ")
        color_command = render_str(
            f"b`{command_list.pop(0)}`<ok> b`{command_list.pop(0)}`<goldenrod> "
        )

        less_len = len(command_list)
        idx = 0
        while idx < less_len:
            if command_list[idx].startswith("-"):
                temp = []
                while idx < less_len and command_list[idx].startswith("-"):
                    temp.append(command_list[idx])
                    idx += 1
                color_command += render_str(f"`{' '.join(temp)}`<sky_blue> ")
            else:
                while idx < less_len and not command_list[idx].startswith("-"):
                    color_command += command_list[idx] + " "
                    idx += 1

        return color_command

    def process_command(
        self, command_: str, args: Optional[Union[list, tuple]] = None
    ) -> None:
        """Process command and arguments.

        Args:
            command_ (str): short command string
            args (list|None, optional): command arguments. Defaults to None.

        Raises:
            SystemExit: not git.
            SystemExit: short command not right.
        """

        option: Optional[dict] = self.cmds.get(command_, None)

        # Invalid, if need suggest.
        if option is None:
            print(
                render_str(
                    "Don't support this command, please try `g --show-commands`<gold>"
                )
            )

            if self.use_recommend:  # check config.
                predicted_command = similar_command(command_, self.cmds.keys())
                if confirm(
                    render_str(
                        f":thinking: The wanted command is `{predicted_command}`<ok> ?[y/n]:"
                    )
                ):
                    self.process_command(predicted_command, args=args)

            return None

        command = option.get("command", None)
        # Has no command can be executed.
        if not command:
            print(
                render_str(
                    "`Invalid custom short command, nothing can to exec.`<error>"
                )
            )
            return None

        if not option.get("has_arguments", False):
            if args:
                print(
                    render_str(
                        f"`The command does not accept parameters. Discard {args}.`<error>"
                    )
                )
                args = []

        _type = option.get("type", "command")
        if _type == "func":
            try:
                command(args)
            except Exception as e:
                print(render_str(f"`{e}`<error>"))
        else:  # is command.
            if args:
                args_str = " ".join(args)
                command = " ".join([command, args_str])
            if self.show_original:
                print(
                    "{0}  {1}".format(Emoji.rainbow, self.color_command(command)),
                )
            run_cmd(command)

    ################################
    # Print command help message.
    ################################
    def _generate_help_by_key(self, _key: str, use_color: bool = True) -> str:
        """Generate one help by given key.

        Args:
            _key (str): Short command string.
            use_color (bool, optional): Whether color help message. Defaults to True.

        Returns:
            (str): Help message of one command.
        """

        _msg: str = "    {key_color}{:<9}{reset}{}{command_color}{}{reset}"
        if use_color:
            _key_color = Color.by_name("ok")
            _command_color = Color.by_name("gold")
        else:
            _key_color = _command_color = ""

        # Get help message and command.
        _help: str = self.cmds[_key].get("help", "")
        try:
            # must have key `command`.
            _command = self.cmds[_key]["command"]
        except:
            raise ValueError("The `command` key can not be empty.")

        # Process help.
        _help = _help + "\n" if _help else ""

        # Process command.
        if callable(_command):
            _command = "Callable: %s" % _command.__name__

        _command = shorten(_command, 70, placeholder="...")
        _command = " " * 13 + _command if _help else _command

        # Splicing and return.
        return _msg.format(
            _key,
            _help,
            _command,
            key_color=_key_color,
            command_color=_command_color,
            reset=Fx.reset,
        )

    def command_help(self) -> None:
        """Print help message."""
        print("These are short commands that can replace git operations:")
        for key in self.cmds.keys():
            msg = self._generate_help_by_key(key)
            print(msg)

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
            print(
                render_str(
                    "`There is no such type.`<error>\n"
                    "Please use `git --types`<ok> to view the supported types."
                )
            )

            if self.use_recommend:
                predicted_type = similar_command(
                    command_type, CommandType.__members__.keys()
                )
                if confirm(
                    render_str(
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
                print(msg)

    @classmethod
    def type_help(cls) -> None:
        """Print all command types with random color."""
        for member in CommandType:
            print(
                "{0}{1}  ".format(
                    Color.fg(
                        random.randint(70, 255),
                        random.randint(70, 255),
                        random.randint(70, 255),
                    ),
                    member.value,
                ),
                end="",
            )
        print(Fx.reset)
