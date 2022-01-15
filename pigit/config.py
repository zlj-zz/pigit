# -*- coding:utf-8 -*-

import os
import logging
import textwrap
from distutils.util import strtobool

from .common import confirm, is_color
from .common.singleton import Singleton

Log = logging.getLogger(__name__)

CONF_ERROR = "==error=="


class ConfigError(Exception):
    """Config error. Using by `Config`."""

    pass


class Config(object, metaclass=Singleton):
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

        # Show original git command.
        gitprocessor_show_original={gitprocessor_show_original}

        # Is it recommended to correct when entering wrong commands.
        gitprocessor_use_recommend={gitprocessor_use_recommend}

        # Whether color is enabled in interactive mode.
        gitprocessor_interactive_color={gitprocessor_interactive_color}

        # Display time of help information in interactive mode, 0 is permanent.
        gitprocessor_interactive_help_showtime={gitprocessor_interactive_help_showtime}

        # Whether to use the ignore configuration of the `.gitignore` file.
        codecounter_use_gitignore={codecounter_use_gitignore}

        # Whether show files that cannot be counted.
        codecounter_show_invalid={codecounter_show_invalid}

        # Whether show files icons. Font support required, like: 'Nerd Font'
        codecounter_show_icon={codecounter_show_icon}

        # Output format of statistical results.
        # Supported: [table, simple]
        # When the command line width is not enough, the `simple ` format is forced.
        codecounter_result_format={codecounter_result_format}

        # Timeout for getting `.gitignore` template from net.
        gitignore_generator_timeout={gitignore_generator_timeout}

        # Git local config print format.
        # Supported: [table, normal]
        git_config_format={git_config_format}

        # Control which parts need to be displayed when viewing git repository information.
        repository_show_path={repository_show_path}
        repository_show_remote={repository_show_remote}
        repository_show_branchs={repository_show_branchs}
        repository_show_lastest_log={repository_show_lastest_log}
        repository_show_summary={repository_show_summary}

        # Whether with color when use `-h` get help message.
        help_use_color={help_use_color}

        # The max line width when use `-h` get help message.
        help_max_line_width={help_max_line_width}

        # Whether run PIGIT in debug mode.
        debug_mode={debug_mode}

        # Whether output log in terminal.
        stream_output_log={stream_output_log}

        """
    )

    # yapf: disable
    _keys :list[str]= [
        'gitprocessor_show_original', 'gitprocessor_use_recommend',
        'gitprocessor_interactive_color', 'gitprocessor_interactive_help_showtime',
        'codecounter_use_gitignore', 'codecounter_show_invalid',
        'codecounter_result_format', 'codecounter_show_icon',
        'gitignore_generator_timeout',
        'git_config_format',
        'repository_show_path', 'repository_show_remote', 'repository_show_branchs',
        'repository_show_lastest_log', 'repository_show_summary',
        'help_use_color', 'help_max_line_width',
        'debug_mode', 'stream_output_log'
    ]
    # yapf: enable

    # config default values.
    gitprocessor_show_original: bool = True
    gitprocessor_use_recommend: bool = True
    gitprocessor_interactive_color: bool = True
    gitprocessor_interactive_help_showtime: float = 1.5

    codecounter_use_gitignore: bool = True
    codecounter_show_invalid: bool = False
    codecounter_show_icon: bool = False
    codecounter_result_format: str = "table"  # table, simple
    _supported_result_format: list = ["table", "simple"]

    gitignore_generator_timeout: int = 60

    git_config_format: str = "table"
    _supported_git_config_format: list = ["normal", "table"]

    repository_show_path: bool = True
    repository_show_remote: bool = True
    repository_show_branchs: bool = True
    repository_show_lastest_log: bool = True
    repository_show_summary: bool = False

    help_use_color: bool = True
    help_max_line_width: int = 90

    debug_mode: bool = False
    stream_output_log: bool = False

    # Store warning messages.
    warnings: list = []

    def __init__(
        self, path: str, version: str = "unknown", auto_load: bool = True
    ) -> None:
        super(Config, self).__init__()

        self.config_file_path: str = path
        self.current_version: str = version
        self.conf: dict = {}

        if auto_load:
            self.load_config()

    def output_warnings(self):
        """Output config warning info and return self object.

        Returns:
            self (Config): single `Config` object.
        """

        if self.warnings:
            print("Config Warning Info")
            print("=" * 30)
            for warning in self.warnings:
                print(warning)
            print("=" * 30)
            self.warnings = []

        return self

    def load_config(self) -> None:
        try:
            self.read_config()
        except Exception as e:
            Log.error(str(e) + str(e.__traceback__))
            self.warnings.append("Can not load the config file.")

        self.parse_conf()

        # setting config.
        for key in self._keys:
            if key in self.conf.keys() and self.conf[key] != CONF_ERROR:
                setattr(self, key, self.conf[key])
            else:
                self.conf[key] = getattr(self, key)

    def read_config(self) -> None:
        new_config = self.conf
        config_file = self.config_file_path

        with open(config_file) as cf:
            for line in cf:
                line = line.strip()
                if line.startswith("#? Config"):
                    new_config["version"] = line[line.find("v. ") + 3 :]
                    continue
                if line.startswith("#"):
                    # comment line.
                    continue
                if "=" not in line:
                    # invalid line.
                    continue
                key, line = line.split("=", maxsplit=1)

                # processing.
                key = key.strip()
                line = line.strip().strip('"')

                # checking.
                if key not in self._keys:
                    self.warnings.append("'{0}' is not be supported!".format(key))
                    continue
                elif type(getattr(self, key)) == int:
                    try:
                        new_config[key] = int(line)
                    except ValueError:
                        self.warnings.append(
                            'Config key "{0}" should be an integer!'.format(key)
                        )
                elif type(getattr(self, key)) == float:
                    try:
                        new_config[key] = float(line)
                    except ValueError:
                        self.warnings.append(
                            'Config key "{0}" should be an float!'.format(key)
                        )
                elif type(getattr(self, key)) == bool:
                    try:
                        # True values are y, yes, t, true, on and 1;
                        # false values are n, no, f, false, off and 0.
                        # Raises ValueError if val is anything else.
                        new_config[key] = bool(strtobool(line))
                    except ValueError:
                        self.warnings.append(
                            'Config key "{0}" can only be True or False!'.format(key)
                        )
                elif type(getattr(self, key)) == str:
                    if "color" in key and not is_color(line):
                        self.warnings.append(
                            'Config key "{0}" should be RGB string, like: #FF0000'.format(
                                key
                            )
                        )
                        continue
                    new_config[key] = str(line)

    def parse_conf(self) -> None:
        new_config = self.conf

        if (  # check codecounter output format whether supported.
            "codecounter_result_format" in new_config
            and new_config["codecounter_result_format"]
            not in self._supported_result_format
        ):
            new_config["codecounter_result_format"] = CONF_ERROR
            self.warnings.append(
                'Config key "{0}" support must in {1}'.format(
                    "codecounter_result_format", self._supported_result_format
                )
            )

        if (
            "git_config_format" in new_config
            and new_config["git_config_format"] not in self._supported_git_config_format
        ):
            new_config["git_config_format"] = CONF_ERROR
            self.warnings.append(
                'Config key "{0}" support must in {1}'.format(
                    "git_config_format", self._supported_git_config_format
                )
            )

        version = self.current_version
        if "version" in new_config and not (
            # If unknown current version or
            # If the version is right or
            # If current version is a [beta, alpha, dev] verstion then will not tip.
            # Else if version is not right will tip.
            version == "unknown"
            or new_config["version"] == version
            or "beta" in version
            or "alpha" in version
            or "dev" in version
        ):
            print(new_config["version"])
            self.warnings.append(
                "The current configuration file is not up-to-date."
                "You'd better recreate it."
            )

    def create_config_template(self) -> None:
        parent_dir = os.path.dirname(self.config_file_path)
        if not os.path.isdir(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        if os.path.exists(self.config_file_path) and not confirm(
            "Configuration exists, overwrite? [y/n]"
        ):
            return None

        # Try to load already has config.
        self.load_config()
        self.conf["version"] = self.current_version

        # Write config. Will save before custom setting.
        try:
            with open(
                self.config_file_path,
                "w" if os.path.isfile(self.config_file_path) else "x",
            ) as f:
                f.write(self.CONFIG_TEMPLATE.format(**self.conf))
        except Exception as e:
            Log.error(str(e) + str(e.__traceback__))
            print("Fail to create config.")
        else:
            print("Successful.")
