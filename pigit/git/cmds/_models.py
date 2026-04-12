# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_models.py
Description: Data models for cmd_new command system.
Author: Zev
Date: 2026-04-10
"""

from dataclasses import dataclass, field
from typing import Union, Optional, Callable, Protocol
from enum import Enum, auto


class CommandCategory(Enum):
    """Command categories for organization and filtering."""

    BRANCH = "branch"
    COMMIT = "commit"
    INDEX = "index"
    WORKING_TREE = "working_tree"
    REMOTE = "remote"
    PUSH = "push"
    FETCH = "fetch"
    LOG = "log"
    STASH = "stash"
    TAG = "tag"
    MERGE = "merge"
    CONFLICT = "conflict"
    SUBMODULE = "submodule"
    SETTINGS = "settings"
    ALIAS = "alias"
    SCRIPT = "script"


class SecurityLevel(Enum):
    """Security levels for command classification."""

    SAFE = auto()
    NORMAL = auto()
    DANGEROUS = auto()
    DESTRUCTIVE = auto()


class CommandSource(Enum):
    """Command source enum for tracing command creation method."""

    BUILTIN = "builtin"
    ALIAS = "alias"
    SCRIPT = "script"
    OVERRIDE = "override"


@dataclass(frozen=True)
class CommandMeta:
    """Command metadata containing all descriptive information.

    Attributes:
        short: Short command name, supports hierarchical naming like "b.c"
        category: Command category for grouping
        help: Help text describing command purpose
        has_args: Whether command accepts arguments
        dangerous: Whether this is a dangerous operation
        confirm_msg: Custom confirmation prompt message
        examples: List of usage examples
        related: List of related commands
        deprecated: Whether command is deprecated
        deprecated_use: Alternative command to use instead
        security_level: Security classification level
        source: Command source indicating how the command was created
        is_user_defined: Whether this command was created by the user
    """

    short: str
    category: CommandCategory
    help: str
    has_args: bool = False
    dangerous: bool = False
    confirm_msg: str = ""
    examples: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    deprecated: bool = False
    deprecated_use: str = ""
    security_level: SecurityLevel = SecurityLevel.SAFE
    source: CommandSource = CommandSource.BUILTIN
    is_user_defined: bool = False


@dataclass
class ScriptConfig:
    """Script configuration corresponding to TOML [cmd_new.scripts.name].

    Attributes:
        steps: Script steps (required)
        help: Help text for the script
        category: Functional category, defaults to "script"
        dangerous: Whether the script is dangerous
        confirm_msg: Confirmation message for dangerous scripts
        examples: Usage examples
    """

    steps: list[str]
    help: str = ""
    category: str = "script"
    dangerous: bool = False
    confirm_msg: str = ""
    examples: list[str] = field(default_factory=list)


@dataclass
class CommandDef:
    """Command definition combining metadata with execution handler.

    Attributes:
        meta: Command metadata
        handler: Command string or callable function
    """

    meta: CommandMeta
    handler: Union[str, Callable[[list[str]], str], ScriptConfig]


@dataclass
class ResolvedCommand:
    """Resolved command containing resolution information.

    Attributes:
        name: Original input command name
        resolved: Resolved command name (after alias expansion)
        definition: Command definition
        is_alias: Whether resolved through alias
        alias_chain: Chain of alias resolutions
    """

    name: str
    resolved: str
    definition: CommandDef
    is_alias: bool = False
    alias_chain: list[str] = field(default_factory=list)


@dataclass
class CompletionItem:
    """Completion item for tab completion.

    Attributes:
        value: Completion value
        display: Display text
        description: Description text
        priority: Priority for sorting (higher = earlier)
    """

    value: str
    display: str
    description: str
    priority: int = 0


class ValidationResult:
    """Result of command validation."""

    def __init__(self, is_valid: bool, errors: Optional[list[str]] = None):
        self.is_valid = is_valid
        self.errors = errors or []

    def __bool__(self) -> bool:
        return self.is_valid


class CommandExecutor(Protocol):
    """Protocol for command executors."""

    def __call__(self, args: list[str]) -> str:
        """Execute command with arguments.

        Args:
            args: Command arguments

        Returns:
            Command output as string
        """
        ...
