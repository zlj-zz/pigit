# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_registry.py
Description: Command registry core for cmd_new.
Author: Project Team
Date: 2026-04-10
"""

from typing import Optional, Callable
from threading import Lock

from ._models import CommandDef, CommandCategory, ValidationResult
from ._validators import CompositeValidator


class RegistryError(Exception):
    """Registry operation error."""

    pass


class CommandRegistry:
    """Command registration center.

    This is a thread-safe singleton registry where decorators
    register command definitions.
    """

    _instance: "Optional[CommandRegistry]" = None
    _lock: Lock = Lock()

    def __new__(cls) -> "CommandRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._commands: dict[str, CommandDef] = {}
        self._aliases: dict[str, str] = {}
        self._dangerous: set[str] = set()
        self._by_category: dict[CommandCategory, set[str]] = {
            cat: set() for cat in CommandCategory
        }
        self._validator = CompositeValidator()
        self._initialized = True

    def register(self, cmd_def: CommandDef) -> ValidationResult:
        """Register a command definition.

        Args:
            cmd_def: Command definition to register

        Returns:
            ValidationResult indicating success or failure

        Raises:
            RegistryError: If command already exists
        """
        result = self._validator.validate(cmd_def)
        if not result.is_valid:
            return result

        name = cmd_def.meta.short

        if name in self._commands:
            raise RegistryError(f"Command '{name}' already registered")

        if name in self._aliases:
            raise RegistryError(f"Name '{name}' is already an alias")

        self._commands[name] = cmd_def
        self._by_category[cmd_def.meta.category].add(name)

        if cmd_def.meta.dangerous:
            self._dangerous.add(name)

        return ValidationResult(True)

    def add_alias(self, alias: str, target: str) -> None:
        """Add an alias mapping.

        Args:
            alias: Alias name
            target: Target command name

        Raises:
            RegistryError: If alias conflicts with existing command
        """
        if alias in self._commands:
            raise RegistryError(f"Cannot alias '{alias}': already a command")

        if alias in self._aliases:
            raise RegistryError(f"Alias '{alias}' already exists")

        self._aliases[alias] = target

    def get(self, name: str) -> Optional[CommandDef]:
        """Get command definition by name.

        Args:
            name: Command name

        Returns:
            CommandDef if found, None otherwise
        """
        return self._commands.get(name)

    def get_all(self, category: Optional[CommandCategory] = None) -> list[CommandDef]:
        """Get all command definitions.

        Args:
            category: Optional category filter

        Returns:
            List of command definitions
        """
        if category:
            return [
                self._commands[name]
                for name in self._by_category.get(category, set())
                if name in self._commands
            ]

        return list(self._commands.values())

    def get_dangerous(self) -> list[CommandDef]:
        """Get all dangerous command definitions.

        Returns:
            List of dangerous command definitions
        """
        return [
            self._commands[name] for name in self._dangerous if name in self._commands
        ]

    def get_aliases(self) -> dict[str, str]:
        """Get all alias mappings.

        Returns:
            Dictionary of alias -> target
        """
        return self._aliases.copy()

    def is_registered(self, name: str) -> bool:
        """Check if command is registered.

        Args:
            name: Command name

        Returns:
            True if registered
        """
        return name in self._commands

    def is_alias(self, name: str) -> bool:
        """Check if name is an alias.

        Args:
            name: Name to check

        Returns:
            True if alias
        """
        return name in self._aliases

    def clear(self) -> None:
        """Clear all registrations (for testing)."""
        self._commands.clear()
        self._aliases.clear()
        self._dangerous.clear()
        for cat in self._by_category:
            self._by_category[cat].clear()


def get_registry() -> CommandRegistry:
    """Get the global command registry instance.

    Returns:
        CommandRegistry singleton
    """
    return CommandRegistry()
