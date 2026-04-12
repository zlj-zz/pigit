# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_config_loader.py
Description: User configuration loading for cmd_new aliases and overrides.
Author: Zev
Date: 2026-04-10
"""

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union, Optional, Any

from ._models import (
    ScriptConfig,
    CommandMeta,
    CommandDef,
    CommandCategory,
    CommandSource,
)


@dataclass
class UserCommandConfig:
    """User command configuration.

    Attributes:
        aliases: User-defined command aliases (name -> target command)
        scripts: Multi-step command scripts (name -> ScriptConfig)
        overrides: Command handler overrides
        settings: General settings
    """

    aliases: dict[str, str] = field(default_factory=dict)
    scripts: dict[str, ScriptConfig] = field(default_factory=dict)
    overrides: dict[str, str] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_toml(cls, path: Union[str, Path]) -> "UserCommandConfig":
        """Load configuration from TOML file.

        Args:
            path: Path to TOML configuration file

        Returns:
            UserCommandConfig instance
        """
        path = Path(path)

        try:
            with open(path, "rb") as f:
                try:
                    import tomllib

                    data = tomllib.load(f)
                except ImportError:
                    import tomli

                    data = tomli.load(f)
        except FileNotFoundError:
            return cls()
        except ImportError:
            # No TOML support
            return cls()
        except Exception:
            # TOML parse error
            return cls()

        logging.getLogger().debug(f"Loaded configuration: {data}, from path: {path}")
        cmd_new_config = data.get("cmd_new", {})

        # Parse scripts - supports both concise and full formats:
        # Concise: [cmd_new.scripts]
        # myscript = ["cmd1", "cmd2"]
        # Full: [cmd_new.scripts.myscript]
        # steps = ["cmd1", "cmd2"]
        # help = "description"
        # category = "branch"
        scripts = {}
        scripts_config = cmd_new_config.get("scripts", {})
        if isinstance(scripts_config, dict):
            for name, value in scripts_config.items():
                if isinstance(value, list):
                    # Concise form: script_name = ["step1", "step2"]
                    scripts[name] = ScriptConfig(steps=value)
                elif isinstance(value, dict):
                    # Full form: [cmd_new.scripts.name] table
                    scripts[name] = ScriptConfig(
                        steps=value.get("steps", []),
                        help=value.get("help", ""),
                        category=value.get("category", "script"),
                        dangerous=value.get("dangerous", False),
                        confirm_msg=value.get("confirm_msg", ""),
                        examples=value.get("examples", []),
                    )

        config = cls(
            aliases=cmd_new_config.get("aliases", {}),
            scripts=scripts,
            overrides=cmd_new_config.get("overrides", {}),
            settings=cmd_new_config.get("settings", {}),
        )

        # Log loaded commands
        if config.aliases:
            logging.getLogger().debug(
                f"Loaded {len(config.aliases)} command aliases: {list(config.aliases.keys())}"
            )
        if config.scripts:
            logging.getLogger().debug(
                f"Loaded {len(config.scripts)} command scripts: {list(config.scripts.keys())}"
            )
        if config.overrides:
            logging.getLogger().debug(
                f"Loaded {len(config.overrides)} command overrides: {list(config.overrides.keys())}"
            )

        return config

    @classmethod
    def default_path(cls) -> Path:
        """Get default configuration file path.

        Returns:
            Path to default config file
        """
        if os.name == "nt":
            base = Path(os.environ.get("USERPROFILE", ""))
            return base / "pigit" / "pigit.cmds.toml"
        else:
            base = Path.home() / ".config" / "pigit"
            return base / "pigit.cmds.toml"

    def get_alias(self, name: str) -> Optional[str]:
        """Get alias target.

        Args:
            name: Alias name

        Returns:
            Target command or None
        """
        return self.aliases.get(name)

    def has_override(self, name: str) -> bool:
        """Check if command has override.

        Args:
            name: Command name

        Returns:
            True if overridden
        """
        return name in self.overrides

    def get_override(self, name: str) -> Optional[str]:
        """Get override handler.

        Args:
            name: Command name

        Returns:
            Override handler or None
        """
        return self.overrides.get(name)

    def get_script(self, name: str) -> Optional[ScriptConfig]:
        """Get script config.

        Args:
            name: Script name

        Returns:
            ScriptConfig or None
        """
        return self.scripts.get(name)

    def has_script(self, name: str) -> bool:
        """Check if name is a script.

        Args:
            name: Script name

        Returns:
            True if script exists
        """
        return name in self.scripts

    def to_command_defs(self) -> list["CommandDef"]:
        """Convert configuration to command definition list.

        Returns:
            List of CommandDef for aliases and scripts
        """

        commands = []

        # 1. Convert aliases to commands
        for alias_name, target in self.aliases.items():
            commands.append(
                CommandDef(
                    meta=CommandMeta(
                        short=alias_name,
                        category=CommandCategory.ALIAS,
                        help=f"Alias for {target}",
                        source=CommandSource.ALIAS,
                        is_user_defined=True,
                    ),
                    handler=target,  # Store target for alias resolution
                )
            )

        # 2. Convert scripts to commands (using full metadata)
        for name, script in self.scripts.items():
            commands.append(
                CommandDef(
                    meta=CommandMeta(
                        short=name,
                        category=CommandCategory(script.category),
                        help=(
                            script.help or f"User script: {script.steps[0][:30]}..."
                            if script.steps
                            else f"User script: {name}"
                        ),
                        dangerous=script.dangerous,
                        confirm_msg=script.confirm_msg,
                        examples=script.examples,
                        source=CommandSource.SCRIPT,
                        is_user_defined=True,
                    ),
                    handler=script,  # Store ScriptConfig for execution
                )
            )

        return commands


def load_user_config(path: Optional[Union[str, Path]] = None) -> UserCommandConfig:
    """Load user configuration.

    Args:
        path: Optional custom config path

    Returns:
        UserCommandConfig instance
    """
    if path:
        return UserCommandConfig.from_toml(path)

    return UserCommandConfig.from_toml(UserCommandConfig.default_path())
