# -*- coding:utf-8 -*-

import logging
import os
import textwrap
from typing import Any

try:
    import tomllib  # type: ignore
except ImportError:
    import tomli  # type: ignore

from .config_data import (
    ConfigData,
    CmdConfig,
    CounterConfig,
    InfoConfig,
    RepoConfig,
    LogConfig,
)
from .ext.singleton import Singleton
from .ext.utils import confirm, traceback_info


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

        version = "{version}"

        [cmd]

        # (bool) Show original git command.
        display = {cmd_display}

        # (bool) Is it recommended to correct when entering wrong commands.
        recommend = {cmd_recommend}

        [counter]

        # (bool) Whether to use the ignore configuration of the `.gitignore` file.
        use_gitignore = {counter_use_gitignore}

        # (bool) Whether show files that cannot be counted.
        show_invalid = {counter_show_invalid}

        # (bool) Whether show files icons. Font support required, like: 'Nerd Font'
        show_icon = {counter_show_icon}

        # Output format of statistical results. Supported: [table, simple]
        # When the command line width is not enough, the `simple` format is forced.
        format = "{counter_format}"

        [info]

        # Git local config print format. Supported: [table, normal]
        git_config_format = "{git_config_format}"

        # Control which parts need to be displayed when viewing git repository information.
        # Support: (path, remote, branch, log, summary)
        repo_include = {repo_info_include}

        [repo]

        # (bool) Whether auto append path to repos.
        auto_append = {repo_auto_append}

        [log]

        # (bool) Whether run PIGIT in debug mode.
        debug = {log_debug}

        # (bool) Whether output log in terminal.
        output = {log_output}
        """
    )

    _counter_format_candidate: list[str] = ["table", "simple"]
    _git_config_format_candidate: list[str] = ["normal", "table"]

    def __init__(
        self, path: str, version: str = "unknown", auto_load: bool = True
    ) -> None:
        self.config_file_path: str = path
        self.current_version: str = version
        self._data = ConfigData(version=version)
        self._warnings: list[str] = []
        self.log = logging.getLogger()

        if auto_load:
            self.load_config()

    def get(self) -> ConfigData:
        """Return the current configuration data.

        Returns:
            ConfigData instance with all configuration values.
        """
        return self._data

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

    def _load_toml(self, path: str) -> ConfigData:
        """Load configuration from TOML file.

        Args:
            path: Path to the TOML configuration file.

        Returns:
            ConfigData populated from the TOML file.
        """
        with open(path, "rb") as f:
            try:
                raw: dict[str, Any] = tomllib.load(f)
            except NameError:
                raw = tomli.load(f)

        version = raw.get("version", self.current_version)

        # Parse [cmd] section
        cmd_raw = raw.get("cmd", {})
        cmd = CmdConfig(
            display=cmd_raw.get("display", True),
            recommend=cmd_raw.get("recommend", True),
        )

        # Parse [counter] section
        counter_raw = raw.get("counter", {})
        counter_format = counter_raw.get("format", "table")
        if counter_format not in self._counter_format_candidate:
            counter_format = "table"
            self._warnings.append(
                'Config key "counter.format" support must in {}'.format(
                    self._counter_format_candidate
                )
            )
        counter = CounterConfig(
            use_gitignore=counter_raw.get("use_gitignore", True),
            show_invalid=counter_raw.get("show_invalid", False),
            show_icon=counter_raw.get("show_icon", False),
            format=counter_format,
        )

        # Parse [info] section
        info_raw = raw.get("info", {})
        git_config_format = info_raw.get("git_config_format", "table")
        if git_config_format not in self._git_config_format_candidate:
            git_config_format = "table"
            self._warnings.append(
                'Config key "info.git_config_format" support must in {}'.format(
                    self._git_config_format_candidate
                )
            )
        repo_include = info_raw.get("repo_include", ["remote", "branch", "log"])
        if not isinstance(repo_include, list):
            repo_include = ["remote", "branch", "log"]
            self._warnings.append(
                'Config key "info.repo_include" should be a list, using default.'
            )
        info = InfoConfig(
            git_config_format=git_config_format,
            repo_include=repo_include,
        )

        # Parse [repo] section
        repo_raw = raw.get("repo", {})
        repo = RepoConfig(
            auto_append=repo_raw.get("auto_append", True),
        )

        # Parse [log] section
        log_raw = raw.get("log", {})
        log = LogConfig(
            debug=log_raw.get("debug", False),
            output=log_raw.get("output", False),
        )

        # Version check
        if not (
            self.current_version == "unknown"
            or version == self.current_version
            or "beta" in self.current_version
            or "alpha" in self.current_version
            or "dev" in self.current_version
        ):
            self._warnings.append(
                "The current configuration file is not up-to-date."
                "You'd better recreate it."
                f"Config version is '{version}', current version is '{self.current_version}'."
            )

        return ConfigData(
            version=version,
            cmd=cmd,
            counter=counter,
            info=info,
            repo=repo,
            log=log,
        )

    def load_config(self) -> None:
        try:
            self._data = self._load_toml(self.config_file_path)
        except FileNotFoundError:
            self.log.info("Has no custom config file.")
        except Exception:
            self.log.error(traceback_info())
            self._warnings.append(
                f"Can not load the config file. Path: {self.config_file_path}"
            )

    def create_config_template(self) -> bool:
        parent_dir = os.path.dirname(self.config_file_path)
        if not os.path.isdir(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        if os.path.exists(self.config_file_path) and not confirm(
            "Configuration exists, overwrite? [y/n]"
        ):
            return False

        # Use current data (defaults or loaded values)
        data = self._data

        try:
            with open(self.config_file_path, "w") as f:
                f.write(
                    self.CONFIG_TEMPLATE.format(
                        version=self.current_version,
                        cmd_display=str(data.cmd.display).lower(),
                        cmd_recommend=str(data.cmd.recommend).lower(),
                        counter_use_gitignore=str(data.counter.use_gitignore).lower(),
                        counter_show_invalid=str(data.counter.show_invalid).lower(),
                        counter_show_icon=str(data.counter.show_icon).lower(),
                        counter_format=data.counter.format,
                        git_config_format=data.info.git_config_format,
                        repo_info_include=data.info.repo_include,
                        repo_auto_append=str(data.repo.auto_append).lower(),
                        log_debug=str(data.log.debug).lower(),
                        log_output=str(data.log.output).lower(),
                    )
                )
        except Exception:
            self.log.error(traceback_info())
            print("Fail to create config.")
            return False
        else:
            print("Successful.")
            return True
