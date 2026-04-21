# -*- coding: utf-8 -*-
"""
Module: pigit/config_data.py
Description: Typed TOML configuration dataclasses for pigit.
Author: Zev
Date: 2026-04-21
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class CmdConfig:
    display: bool = True
    recommend: bool = True


@dataclass
class CounterConfig:
    use_gitignore: bool = True
    show_invalid: bool = False
    show_icon: bool = False
    format: Literal["table", "simple"] = "table"


@dataclass
class InfoConfig:
    git_config_format: Literal["normal", "table"] = "table"
    repo_include: list[str] = field(default_factory=lambda: ["remote", "branch", "log"])


@dataclass
class RepoConfig:
    auto_append: bool = True


@dataclass
class LogConfig:
    debug: bool = False
    output: bool = False


@dataclass
class ConfigData:
    version: str = "unknown"
    cmd: CmdConfig = field(default_factory=CmdConfig)
    counter: CounterConfig = field(default_factory=CounterConfig)
    info: InfoConfig = field(default_factory=InfoConfig)
    repo: RepoConfig = field(default_factory=RepoConfig)
    log: LogConfig = field(default_factory=LogConfig)
