# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_validators.py
Description: Command validation system for cmd_new.
Author: Project Team
Date: 2026-04-10
"""

import re
from typing import Optional
from abc import ABC, abstractmethod

from ._models import CommandDef, ValidationResult, SecurityLevel


class CommandValidator(ABC):
    """Abstract base class for command validators.

    Validators check command definitions for correctness and compliance
    with naming conventions and security policies.
    """

    @abstractmethod
    def validate(self, cmd_def: CommandDef) -> ValidationResult:
        """Validate a command definition.

        Args:
            cmd_def: Command definition to validate

        Returns:
            ValidationResult indicating success or failure with errors
        """
        pass


class CommandNameValidator(CommandValidator):
    """Validator for command name format.

    Rules:
        - Letters, numbers, dots, and underscores (case-sensitive)
        - Cannot start or end with dot
        - No consecutive dots
        - Length between 1 and 32 characters
    """

    _PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)*$")
    _MAX_LENGTH = 32
    _FORBIDDEN_NAMES = {"help", "exit", "quit", "list"}

    def validate(self, cmd_def: CommandDef) -> ValidationResult:
        """Validate command name format."""
        name = cmd_def.meta.short
        errors = []

        if not name:
            errors.append("Command name cannot be empty")
        elif len(name) > self._MAX_LENGTH:
            errors.append(f"Command name too long (max {self._MAX_LENGTH} chars)")
        elif not self._PATTERN.match(name):
            errors.append(
                "Invalid command name format. Only letters, numbers, "
                "underscores, and dots allowed. Cannot start/end with dot."
            )
        elif name in self._FORBIDDEN_NAMES:
            errors.append(f"Command name '{name}' is reserved")

        return ValidationResult(len(errors) == 0, errors)


class DangerousCommandValidator(CommandValidator):
    """Validator for dangerous command configuration.

    Ensures dangerous commands have proper confirmation messages
    and security level classifications.
    """

    def validate(self, cmd_def: CommandDef) -> ValidationResult:
        """Validate dangerous command configuration."""
        errors = []
        meta = cmd_def.meta

        if meta.dangerous and not meta.confirm_msg:
            errors.append(f"Dangerous command '{meta.short}' must have confirm_msg")

        if meta.dangerous and meta.security_level == SecurityLevel.SAFE:
            errors.append(
                f"Dangerous command '{meta.short}' must have " "security_level > SAFE"
            )

        return ValidationResult(len(errors) == 0, errors)


class CompositeValidator(CommandValidator):
    """Composite validator that runs multiple validation rules."""

    def __init__(self, validators: Optional[list[CommandValidator]] = None):
        self._validators = validators or [
            CommandNameValidator(),
            DangerousCommandValidator(),
        ]

    def validate(self, cmd_def: CommandDef) -> ValidationResult:
        """Run all validators and collect errors."""
        all_errors = []

        for validator in self._validators:
            result = validator.validate(cmd_def)
            if not result.is_valid:
                all_errors.extend(result.errors)

        return ValidationResult(len(all_errors) == 0, all_errors)
