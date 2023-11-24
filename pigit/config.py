# -*- coding:utf-8 -*-

import os
import re
import textwrap
from typing import Any, List, Literal, Dict

from .ext.log import logger
from .ext.singleton import Singleton
from .ext.utils import confirm, strtobool ,traceback_info


CONF_ERROR = "==error=="


class ConfigError(Exception):
    """Config error. Using by `Config`."""


class Config(metaclass=Singleton):
    """PIGIT configuration class."""

    CONFIG_TEMPLATE: str = textwrap.dedent(
        """\
        #? Config file for pigit v. {version}

        #  ____ ___ ____ ___ _____                            __ _
        # |  _ \\_ _/ ___|_ _|_   _|           ___ ___  _ __  / _(_) __ _
        # | |_) | | |  _ | |  | |_____ _____ / __/ _ \\| '_ \\| |_| |/ _` |
        # |  __/| | |_| || |  | |_____|_____| (_| (_) | | | |  _| | (_| |
        # |_|  |___\\____|___| |_|            \\___\\___/|_| |_|_| |_|\\__, |
        #                                     {version:>20} |___/
        # Git-tools -- pigit configuration.

        # (bool) Show original git command.
        cmd_display={cmd_display}

        # (bool) Is it recommended to correct when entering wrong commands.
        cmd_recommend={cmd_recommend}

        # (float) Display time of help information in interactive mode.
        tui_help_showtime={tui_help_showtime}

        # (bool) Whether show the icon of file.
        # The effect is not perfect and needs improvement.
        tui_files_icon={tui_files_icon}

        # (bool) Whether to use the ignore configuration of the `.gitignore` file.
        counter_use_gitignore={counter_use_gitignore}

        # (bool) Whether show files that cannot be counted.
        counter_show_invalid={counter_show_invalid}

        # (bool) Whether show files icons. Font support required, like: 'Nerd Font'
        counter_show_icon={counter_show_icon}

        # Output format of statistical results. Supported: [table, simple]
        # When the command line width is not enough, the `simple ` format is forced.
        counter_format={counter_format}

        # Git local config print format. Supported: [table, normal]
        git_config_format={git_config_format}

        # Control which parts need to be displayed when viewing git repository information.
        # Support: (path,remote,branch,log,summary)
        repo_info_include={repo_info_include}

        # (bool) Whether auto append path to repos.
        repo_auto_append={repo_auto_append}

        # (bool) Whether run PIGIT in debug mode.
        log_debug={log_debug}

        # (bool) Whether output log in terminal.
        log_output={log_output}

        """
    )

    _KEYS: List[str] = [
        "cmd_display",
        "cmd_recommend",
        "tui_help_showtime",
        "tui_files_icon",
        "counter_use_gitignore",
        "counter_show_invalid",
        "counter_show_icon",
        "counter_format",
        "git_config_format",
        "repo_info_include",
        "repo_auto_append",
        "log_debug",
        "log_output",
    ]

    # ======================
    # config default values.
    # ======================

    # cmd processor conf
    cmd_display: bool = True
    cmd_recommend: bool = True

    # tui conf
    tui_help_showtime: float = 1.5
    tui_files_icon: bool = False

    # code counter conf
    counter_use_gitignore: bool = True
    counter_show_invalid: bool = False
    counter_show_icon: bool = False
    counter_format: Literal["table", "simple"] = "table"
    _counter_format_candidate: List = ["table", "simple"]

    # info conf
    git_config_format: Literal["normal", "table"] = "table"
    _git_config_format_candidate: List = ["normal", "table"]

    repo_info_include: List[str] = ["remote", "branch", "log"]

    # repo conf
    repo_auto_append: bool = False

    # setting conf
    log_debug: bool = False
    log_output: bool = False

    # Store warning messages.
    _warnings: List = []

    def __init__(
        self, path: str, version: str = "unknown", auto_load: bool = True
    ) -> None:
        self.config_file_path: str = path
        self.current_version: str = version
        self.conf: Dict[str, Any] = {}

        if auto_load:
            self.load_config()

    def output_warnings(self) -> "Config":
        """Output config warning info and return self object.

        Returns:
            self (Config): single `Config` object.
        """

        if self._warnings:
            print("#", "::Config Warning Info::")
            print("#", "=" * 30)
            for warning in self._warnings:
                print("#", warning)
            print("#", "=" * 30)
            self._warnings = []

        return self

    def check_and_set_value(self, key: str, value: str, config: Dict) -> None:
        if key not in self._KEYS:
            self._warnings.append(f"'{key}' is not be supported!")
            return

        v_type = type(getattr(self, key))
        if v_type == int:
            try:
                config[key] = int(value)
            except ValueError:
                self._warnings.append(f'Config key "{key}" should be an integer!')
        elif v_type == float:
            try:
                config[key] = float(value)
            except ValueError:
                self._warnings.append(f'Config key "{key}" should be a float!')
        elif v_type == bool:
            try:
                # True values are y, yes, t, true, on and 1;
                # false values are n, no, f, false, off and 0.
                # Raises ValueError if val is anything else.
                config[key] = bool(strtobool(value))
            except ValueError:
                self._warnings.append(f'Config key "{key}" can only be True or False!')
        elif v_type == str:
            if "color" in key and not re.match(r"^#[0-9a-fA-F]6$", value):
                self._warnings.append(
                    f'Config key "{key}" should be RGB string, like: "#FF0000".'
                )
            else:
                config[key] = value
        elif v_type == list:
            if re.match(r"^\[[\w\s0-9\'\"_]+,?([\s\w0-9\'\"_]+,?)*\]$", value):
                config[key] = eval(value)
            else:
                self._warnings.append(f'Config key "{key}" not support `{value}`.')

    def read_config(self) -> None:
        config = self.conf
        config_file = self.config_file_path

        if not os.path.isfile(config_file):
            logger(__name__).info("Has no custom config file.")
            return

        with open(config_file) as cf:
            for line in cf:
                line = line.strip()
                if line.startswith("#? Config"):
                    config["version"] = line[line.find("v. ") + 3 :]
                    continue
                if line.startswith("#"):
                    # comment line.
                    continue
                if "=" not in line:
                    # invalid line.
                    continue

                # remove line comment.
                if line_comment_idx := line.find("#") > 0:
                    line = line[:line_comment_idx]

                # processing.
                key_str, value_str = line.split("=", maxsplit=1)
                key_str = key_str.strip()
                value_str = value_str.strip().strip('"')

                # checking.
                self.check_and_set_value(key_str, value_str, config)

    def parse_config(self) -> None:
        config = self.conf

        if (  # check code-counter output format whether supported.
            "counter_format" in config
            and config["counter_format"] not in self._counter_format_candidate
        ):
            config["counter_format"] = CONF_ERROR
            self._warnings.append(
                'Config key "{0}" support must in {1}'.format(
                    "counter_format", self._counter_format_candidate
                )
            )

        if (
            "git_config_format" in config
            and config["git_config_format"] not in self._git_config_format_candidate
        ):
            config["git_config_format"] = CONF_ERROR
            self._warnings.append(
                'Config key "{0}" support must in {1}'.format(
                    "git_config_format", self._git_config_format_candidate
                )
            )

        version = self.current_version
        if "version" in config and not (
            # If unknown current version or
            # If the version is right or
            # If current version is a [beta, alpha, dev] version then will not tip.
            # Else if version is not right will tip.
            version == "unknown"
            or config["version"] == version
            or "beta" in version
            or "alpha" in version
            or "dev" in version
        ):
            self._warnings.append(
                "The current configuration file is not up-to-date."
                "You'd better recreate it."
                f"Config version is '{config['version']}', current version is '{version}'."
            )

    def load_config(self) -> None:
        try:
            self.read_config()
        except Exception:
            logger(__name__).error(traceback_info())
            self._warnings.append(
                f"Can not load the config file. Path: {self.config_file_path}"
            )

        self.parse_config()

        # setting config.
        for key in self._KEYS:
            if key in self.conf.keys() and self.conf[key] != CONF_ERROR:
                # update default for using.
                setattr(self, key, self.conf[key])
            else:
                # append default to conf for written.
                self.conf[key] = getattr(self, key)

    def create_config_template(self) -> bool:
        parent_dir = os.path.dirname(self.config_file_path)
        if not os.path.isdir(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        if os.path.exists(self.config_file_path) and not confirm(
            "Configuration exists, overwrite? [y/n]"
        ):
            return False

        # Try to load already has config.
        self.load_config()
        self.conf["version"] = self.current_version

        # Write config with already exist custom settings.
        try:
            with open(
                self.config_file_path,
                "w" if os.path.isfile(self.config_file_path) else "x",
            ) as f:
                f.write(self.CONFIG_TEMPLATE.format(**self.conf))
        except Exception:
            logger(__name__).error(traceback_info())
            print("Fail to create config.")
            return False
        else:
            print("Successful.")
            return True
