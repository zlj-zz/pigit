# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_decorators.py
Description: Command and alias decorators for cmd_new.
Author: Zev
Date: 2026-04-10
"""

from typing import TYPE_CHECKING, Union, Optional, Callable
from functools import wraps

from ._models import CommandDef, CommandMeta, CommandCategory, SecurityLevel
from ._registry import get_registry


if TYPE_CHECKING:
    from ._security import SecureExecutor


def command(
    short: str,
    category: CommandCategory,
    help: str,
    has_args: bool = False,
    dangerous: bool = False,
    confirm_msg: str = "",
    examples: Optional[list[str]] = None,
    related: Optional[list[str]] = None,
    deprecated: bool = False,
    deprecated_use: str = "",
    security_level: SecurityLevel = SecurityLevel.SAFE,
) -> Callable[[Union[Callable, str]], CommandDef]:
    """Decorator to register a command.

    Args:
        short: Short command name (supports hierarchical like "b.c")
        category: Command category
        help: Help text
        has_args: Whether command accepts arguments
        dangerous: Whether this is a dangerous operation
        confirm_msg: Custom confirmation message
        examples: Usage examples
        related: Related commands
        deprecated: Whether deprecated
        deprecated_use: Alternative command
        security_level: Security classification

    Returns:
        Decorator function
    """

    def decorator(handler: Union[Callable, str]) -> CommandDef:
        meta = CommandMeta(
            short=short,
            category=category,
            help=help,
            has_args=has_args,
            dangerous=dangerous,
            confirm_msg=confirm_msg,
            examples=examples or [],
            related=related or [],
            deprecated=deprecated,
            deprecated_use=deprecated_use,
            security_level=security_level,
        )

        cmd_def = CommandDef(meta=meta, handler=handler)

        registry = get_registry()
        result = registry.register(cmd_def)

        if not result.is_valid:
            raise ValueError(f"Failed to register command '{short}': {result.errors}")

        return cmd_def

    return decorator


def alias(name: str, target: str) -> Callable[[], None]:
    """Decorator to register an alias.

    Args:
        name: Alias name
        target: Target command name

    Returns:
        Decorator function
    """

    def decorator() -> None:
        registry = get_registry()
        registry.add_alias(name, target)

    # Execute immediately to register alias
    decorator()

    return decorator


# Module-level executor singleton for dangerous decorator
_dangerous_executor: Optional["SecureExecutor"] = None


def _get_dangerous_executor() -> "SecureExecutor":
    """Get or create the shared SecureExecutor for dangerous decorator."""
    global _dangerous_executor
    if _dangerous_executor is None:
        from ._security import SecureExecutor

        _dangerous_executor = SecureExecutor()
    return _dangerous_executor


def dangerous(
    confirm_msg: str = "",
    double_confirm: bool = False,
) -> Callable[[Callable], Callable]:
    """Mark a function as dangerous with confirmation.

    Args:
        confirm_msg: Custom confirmation message
        double_confirm: Whether to require double confirmation

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            executor = _get_dangerous_executor()

            msg = confirm_msg or f"Execute dangerous command '{func.__name__}'?"

            if double_confirm:
                if not executor.confirm(msg, double_confirm=True):
                    return "Cancelled"
            else:
                if not executor.confirm(msg):
                    return "Cancelled"

            return func(*args, **kwargs)

        return wrapper

    return decorator
