from __future__ import annotations

import logging
import os
import textwrap
from typing import Any

import tomllib

from .config_data import (
    ConfigData,
    CmdConfig,
    CounterConfig,
    InfoConfig,
    RepoConfig,
    LogConfig,
    AppConfig,
)
from .ext.singleton import Singleton
from .ext.utils import confirm, traceback_info


class ConfigError(Exception):
    """Config error. Using by `Config`."""


def _flatten_keybindings(raw: dict, prefix: str = "") -> dict:
    """Flatten a nested ``[app.keybindings]`` table into dotted ``"{ns}.{action}"`` keys."""
    out: dict = {}
    for key, value in raw.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(_flatten_keybindings(value, dotted))
        else:
            out[dotted] = value
    return out


class Config(metaclass=Singleton):
    """PIGIT configuration class."""

    CONFIG_TEMPLATE: str = textwrap.dedent("""\
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

        [app]

        # (bool) Observe git metadata and refresh panels when the repo changes.
        repo_observe = {app_repo_observe}

        # (bool) Also observe worktree files for Status list updates.
        observe_worktree = {app_observe_worktree}

        # (bool) Enable word-diff by default in the diff viewer.
        word_diff = {app_word_diff}

        # (str) Status panel default view. Supported: [flat, tree]
        status_view = "{app_status_view}"

        # (bool) Show Status/Stash side diff preview on large screens (>= 120 cols).
        # Ctrl+p on Status/Stash toggles at runtime; this is the startup default only.
        diff_preview_default = {app_diff_preview_default}

        # (bool) Show Branch log-graph preview on large screens (>= 120 cols).
        # Ctrl+p on Branch toggles at runtime; this is the startup default only.
        log_graph_default = {app_log_graph_default}

        # (bool) Show the Commit contribution-graph report below the list on
        # tall screens (> 19 rows). Ctrl+r toggles at runtime.
        commit_report_default = {app_commit_report_default}

        # (bool) Show the footer key-hint bar.
        show_footer = {app_show_footer}

        # (bool) Auto-show Welcome Sheet on first run. Set false to disable.
        # To see Welcome again: delete welcome_seen from state.toml (see STATE_FILE_PATH).
        show_welcome = {app_show_welcome}

        # (bool) Show Nerd Font file icons in the Status list. Needs a
        # Nerd Font terminal; set PIGIT_ICONS=0 to force off.
        file_icons = {app_file_icons}
        {keybindings}
        """)

    _counter_format_candidate: list[str] = ["table", "simple"]
    _git_config_format_candidate: list[str] = ["normal", "table"]
    _status_view_candidate: list[str] = ["flat", "tree"]

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

        Warnings are written to ``stderr`` so they do not contaminate
        ``stdout``-oriented output (e.g. shell completion scripts).

        Returns:
            self (Config): single `Config` object.
        """
        if not self._warnings:
            return self

        import sys
        from shutil import get_terminal_size

        from .termui.cli_output import get_console

        console = get_console()
        term_width, _ = get_terminal_size()
        width = min(72, term_width - 4)
        bar = "━" * width

        print(console.render("@bold(@red(Config Warning))"), file=sys.stderr)
        print(console.render(f"@bold(@red({bar}))"), file=sys.stderr)
        for i, warning in enumerate(self._warnings, 1):
            prefix = f"{i}. "
            indent = " " * (len(prefix) + 2)
            wrapped = textwrap.fill(
                warning,
                width=width - 2,
                initial_indent=f"  {prefix}",
                subsequent_indent=indent,
            )
            print(wrapped, file=sys.stderr)
        print(console.render(f"@bold(@red({bar}))"), file=sys.stderr)
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
            raw: dict[str, Any] = tomllib.load(f)

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

        # Parse [app] (UI settings + nested [app.keybindings])
        app_raw = raw.get("app", {})
        if not isinstance(app_raw, dict):
            app_raw = {}
            self._warnings.append(
                'Config section "app" should be a table, using defaults.'
            )
        if "tui" in raw:
            self._warnings.append(
                "Config section [tui] was renamed to [app]; [tui] is ignored. "
                "Move those keys under [app]."
            )
        if "keybindings" in raw:
            self._warnings.append(
                "Config section [keybindings] moved to [app.keybindings]; "
                "[keybindings] is ignored."
            )
        status_view = app_raw.get("status_view", "tree")
        if status_view not in self._status_view_candidate:
            status_view = "tree"
            self._warnings.append(
                'Config key "app.status_view" support must in {}'.format(
                    self._status_view_candidate
                )
            )
        kb_raw = app_raw.get("keybindings", {})
        if not isinstance(kb_raw, dict):
            kb_raw = {}
            self._warnings.append(
                'Config key "app.keybindings" should be a table, using defaults.'
            )
        if "auto_refresh_interval" in app_raw:
            self._warnings.append(
                'Config key "app.auto_refresh_interval" is ignored; '
                "use app.repo_observe instead."
            )
        app = AppConfig(
            repo_observe=app_raw.get("repo_observe", True),
            observe_worktree=app_raw.get("observe_worktree", True),
            word_diff=app_raw.get("word_diff", True),
            status_view=status_view,
            diff_preview_default=app_raw.get("diff_preview_default", True),
            log_graph_default=app_raw.get("log_graph_default", True),
            commit_report_default=app_raw.get("commit_report_default", True),
            show_footer=app_raw.get("show_footer", True),
            show_welcome=app_raw.get("show_welcome", True),
            # PIGIT_ICONS=0 forces icons off regardless of config (first
            # UI-class env override; kept here so it lives next to parsing).
            file_icons=os.environ.get("PIGIT_ICONS", "") != "0"
            and app_raw.get("file_icons", True),
            keybindings=_flatten_keybindings(kb_raw),
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
                "The current configuration file is not up-to-date. "
                "You'd better recreate it. "
                f"Config version is '{version}', current version is '{self.current_version}'."
            )

        return ConfigData(
            version=version,
            cmd=cmd,
            counter=counter,
            info=info,
            repo=repo,
            log=log,
            app=app,
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

    def create_config_template(self, keybindings_block: str = "") -> bool:
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
                        app_repo_observe=str(data.app.repo_observe).lower(),
                        app_observe_worktree=str(data.app.observe_worktree).lower(),
                        app_word_diff=str(data.app.word_diff).lower(),
                        app_status_view=data.app.status_view,
                        app_diff_preview_default=str(
                            data.app.diff_preview_default
                        ).lower(),
                        app_log_graph_default=str(data.app.log_graph_default).lower(),
                        app_commit_report_default=str(
                            data.app.commit_report_default
                        ).lower(),
                        app_show_footer=str(data.app.show_footer).lower(),
                        app_show_welcome=str(data.app.show_welcome).lower(),
                        app_file_icons=str(data.app.file_icons).lower(),
                        keybindings=keybindings_block,
                    )
                )
        except Exception:
            self.log.error(traceback_info())
            print("Fail to create config.")
            return False
        else:
            print("Successful.")
            return True
