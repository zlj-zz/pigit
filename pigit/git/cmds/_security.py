# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_security.py
Description: Secure command execution and dangerous command handling.
Author: Zev
Date: 2026-04-10
"""

import re
from collections import deque
from dataclasses import dataclass
from typing import Union, Optional, Callable

from pigit.ext.executor import Executor, WAITING
from pigit.ext.executor_factory import ExecutorFactory


class SecurityError(Exception):
    """Security violation error."""

    pass


@dataclass
class SecurityPolicy:
    """Security policy configuration for command execution.

    Attributes:
        require_confirmation: Whether to prompt for confirmation
        require_double_confirm: Whether to require double confirmation
        allowed_in_ci: Whether allowed in CI environment
        audit_log: Whether to log to audit trail
    """

    require_confirmation: bool = True
    require_double_confirm: bool = False
    allowed_in_ci: bool = True
    audit_log: bool = False


class SecureExecutor:
    """Secure command executor preventing injection attacks.

    This executor validates commands against dangerous patterns
    and enforces security policies before execution.
    """

    # Pre-compiled dangerous patterns that could indicate injection
    _DANGEROUS_PATTERNS = [
        re.compile(r";.*rm\s+-rf"),
        re.compile(r"\|\s*sh"),
        re.compile(r"\|\s*bash"),
        re.compile(r"`.*`"),
        re.compile(r"\$\(.*\)"),
        re.compile(r"\$\{.*\}"),
        re.compile(r">\s*/dev/null"),
        re.compile(r"2>&1\s*\|"),
    ]

    # Maximum audit log entries to prevent unbounded growth
    _MAX_AUDIT_LOG_SIZE = 1000

    def __init__(self, base_executor: Optional[Executor] = None):
        self._base = base_executor or ExecutorFactory.get()
        self._audit_log: deque[dict] = deque(maxlen=self._MAX_AUDIT_LOG_SIZE)

    def exec(
        self,
        cmd: Union[str, list[str]],
        args: Optional[list[str]] = None,
        policy: Optional[SecurityPolicy] = None,
    ) -> tuple[int, str]:
        """Execute command securely.

        Args:
            cmd: Command string or list of command parts
            args: Command arguments (if cmd is string, this should be None)
            policy: Security policy to apply

        Returns:
            Tuple of (exit_code, output)

        Raises:
            SecurityError: If command contains dangerous patterns
        """
        policy = policy or SecurityPolicy()

        parts = self._normalize_command(cmd, args)

        if not self._validate_command(parts):
            raise SecurityError(
                f"Command contains dangerous patterns: {' '.join(parts)}"
            )

        if policy.audit_log:
            self._audit_log.append(
                {
                    "command": parts,
                    "policy": policy,
                }
            )

        cmd_str = " ".join(parts)
        exit_code, stderr, stdout = self._base.exec(cmd_str, flags=WAITING)
        output = stdout if stdout else (stderr if stderr else "")
        return exit_code, output

    def _normalize_command(
        self, cmd: Union[str, list[str]], args: Optional[list[str]]
    ) -> list[str]:
        """Normalize command to list format."""
        if isinstance(cmd, list):
            return cmd

        if args:
            return [cmd] + args

        return cmd.split()

    def _validate_command(self, parts: list[str]) -> bool:
        """Validate command against dangerous patterns."""
        cmd_str = " ".join(parts)

        for pattern in self._DANGEROUS_PATTERNS:
            if pattern.search(cmd_str):
                return False

        return True

    def confirm(self, message: str, double_confirm: bool = False) -> bool:
        """Prompt for user confirmation.

        Args:
            message: Confirmation message to display
            double_confirm: Whether to require double confirmation

        Returns:
            True if user confirms, False otherwise
        """
        import sys

        try:
            response = input(f"{message} [y/N]: ").strip().lower()
            if response != "y":
                return False

            if double_confirm:
                response2 = input(
                    "This action cannot be undone. Type 'yes' to confirm: "
                ).strip()
                return response2 == "yes"

            return True
        except (EOFError, KeyboardInterrupt):
            return False

    def get_audit_log(self) -> list[dict]:
        """Get audit log entries."""
        return self._audit_log.copy()
