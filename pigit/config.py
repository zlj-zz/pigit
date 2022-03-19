# -*- coding:utf-8 -*-

from typing import Dict, List
import os, re, textwrap, logging
from distutils.util import strtobool

from .common.utils import confirm, traceback_info
from .common.singleton import Singleton
from .render.style import Color

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

        # (bool) Show original git command.
        cmd_show_original={cmd_show_original}

        # (bool) Is it recommended to correct when entering wrong commands.
        cmd_recommend={cmd_recommend}

        # (float) Display time of help information in interactive mode.
        tui_help_showtime={tui_help_showtime}

        # (bool) Whether to use the ignore configuration of the `.gitignore` file.
        counter_use_gitignore={counter_use_gitignore}

        # (bool) Whether show files that cannot be counted.
        counter_show_invalid={counter_show_invalid}

        # (bool) Whether show files icons. Font support required, like: 'Nerd Font'
        counter_show_icon={counter_show_icon}

        # Output format of statistical results. Supported: [table, simple]
        # When the command line width is not enough, the `simple ` format is forced.
        counter_format={counter_format}

        # (int) Timeout for getting `.gitignore` template from network.
        gitignore_generator_timeout={gitignore_generator_timeout}

        # Git local config print format. Supported: [table, normal]
        git_config_format={git_config_format}

        # Control which parts need to be displayed when viewing git repository information.
        # Support: (path,remote,branch,log,summary)
        repo_info_include={repo_info_include}

        # (bool) Whether auto append path to repos.
        repo_auto_append={repo_auto_append}

        # (bool) Whether run PIGIT in debug mode.
        debug_open={debug_open}

        # (bool) Whether output log in terminal.
        log_output={log_output}

        """
    )

    _keys: List[str] = [
        "cmd_show_original",
        "cmd_recommend",
        "tui_help_showtime",
        "counter_use_gitignore",
        "counter_show_invalid",
        "counter_show_icon",
        "counter_format",
        "gitignore_generator_timeout",
        "git_config_format",
        "repo_info_include",
        "repo_auto_append",
        "debug_open",
        "log_output",
    ]

    #########################
    # config default values.
    #########################

    # cmd processor conf
    cmd_show_original: bool = True
    cmd_recommend: bool = True

    # tui conf
    tui_help_showtime: float = 1.5

    # code counter conf
    counter_use_gitignore: bool = True
    counter_show_invalid: bool = False
    counter_show_icon: bool = False
    counter_format: str = "table"  # table, simple
    _supported_result_format: List = ["table", "simple"]

    # ignore file conf
    gitignore_generator_timeout: int = 60

    # info conf
    git_config_format: str = "table"
    _supported_git_config_format: List = ["normal", "table"]

    repo_info_include: List[str] = ["remote", "branch", "log"]

    # repo conf
    repo_auto_append: bool = False

    # setting conf
    debug_open: bool = False
    log_output: bool = False

    # Store warning messages.
    warnings: List = []

    def __init__(
        self, path: str, version: str = "unknown", auto_load: bool = True
    ) -> None:
        super(Config, self).__init__()

        self.config_file_path: str = path
        self.current_version: str = version
        self.conf: Dict = {}

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
            Log.error(traceback_info())
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
                    self.warnings.append(f"'{key}' is not be supported!")
                    continue
                elif type(getattr(self, key)) == int:
                    try:
                        new_config[key] = int(line)
                    except ValueError:
                        self.warnings.append(
                            f'Config key "{key}" should be an integer!'
                        )
                elif type(getattr(self, key)) == float:
                    try:
                        new_config[key] = float(line)
                    except ValueError:
                        self.warnings.append(f'Config key "{key}" should be a float!')
                elif type(getattr(self, key)) == bool:
                    try:
                        # True values are y, yes, t, true, on and 1;
                        # false values are n, no, f, false, off and 0.
                        # Raises ValueError if val is anything else.
                        new_config[key] = bool(strtobool(line))
                    except ValueError:
                        self.warnings.append(
                            f'Config key "{key}" can only be True or False!'
                        )
                elif type(getattr(self, key)) == str:
                    if "color" in key and not Color.is_color(line):
                        self.warnings.append(
                            f'Config key "{key}" should be RGB string, like: "#FF0000".'
                        )
                        continue
                    new_config[key] = str(line)
                elif type(getattr(self, key)) == list:
                    if re.match(r"^\[[\w\s0-9\'\"_]+,?([\s\w0-9\'\"_]+,?)*\]$", line):
                        new_config[key] = eval(line)
                    else:
                        self.warnings.append(
                            f'Config key "{key}" not support `{line}`.'
                        )

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
            Log.error(traceback_info())
            print("Fail to create config.")
        else:
            print("Successful.")
