"""
Module: pigit/git/cmds/__init__.py
Description: cmd_new command system - unified exports and main processor.
Author: Zev
Date: 2026-04-10
"""

from __future__ import annotations

import os

# Import all command modules to trigger registration
from . import branch
from . import commit
from . import conflict
from . import history
from . import index
from . import merge
from . import push_pull
from . import rebase
from . import remote
from . import settings
from . import submodule
from . import working_tree

# Core exports
from ._models import (
    CommandCategory,
    SecurityLevel,
    CommandSource,
    CommandMeta,
    CommandDef,
    ResolvedCommand,
    CompletionItem,
    ValidationResult,
    ScriptConfig,
)
from ._registry import CommandRegistry, get_registry, RegistryError
from ._resolver import CommandResolver, ResolverError, AliasCycleError
from ._validators import (
    CommandValidator,
    CommandNameValidator,
    DangerousCommandValidator,
    CompositeValidator,
)
from ._security import SecureExecutor, SecurityPolicy, SecurityError
from ._config_loader import UserCommandConfig, load_user_config
from ._decorators import command, alias, dangerous
from ._utils import is_truthy
from ._mru import record_command_use


def register_user_commands(
    registry: CommandRegistry | None = None,
    config: UserCommandConfig | None = None,
) -> None:
    """Register user-defined aliases and scripts into the command registry.

    Args:
        registry: Command registry instance
        config: User configuration
    """
    registry = registry or get_registry()
    config = config or load_user_config()

    for cmd_def in config.to_command_defs():
        try:
            if cmd_def.meta.source == CommandSource.ALIAS and isinstance(
                cmd_def.handler, str
            ):
                registry.add_alias(cmd_def.meta.short, cmd_def.handler)
            registry.register(cmd_def)
        except RegistryError:
            # Skip conflicting entries
            pass


class GitCommandNew:
    """New Git command processor running parallel to GitProxy.

    This class provides the main interface for the new command system,
    integrating registry, resolver, config, validator, and secure executor.
    """

    def __init__(
        self,
        registry: CommandRegistry | None = None,
        resolver: CommandResolver | None = None,
        config: UserCommandConfig | None = None,
        executor: SecureExecutor | None = None,
    ):
        """Initialize GitCommandNew processor.

        Args:
            registry: Command registry instance
            resolver: Command resolver instance
            config: User configuration
            executor: Secure executor instance
        """
        self._registry = registry or get_registry()
        self._resolver = resolver or CommandResolver(self._registry)
        self._config = config or load_user_config()
        self._executor = executor or SecureExecutor()

        # Load user commands from config
        register_user_commands(self._registry, self._config)

    def execute(self, cmd: str, args: list[str] | None = None) -> tuple[int, str]:
        """Execute a command.

        Args:
            cmd: Command name (may include aliases)
            args: Command arguments

        Returns:
            Tuple of (exit_code, output)
        """
        from ._executor import _execute_handler, _execute_override

        args = args or []

        # Check for override first
        if override := self._config.get_override(cmd):
            exit_code, output = _execute_override(
                override, args, self._executor, self._registry, self.execute
            )
            if exit_code == 0:
                record_command_use(cmd)
            return exit_code, output

        try:
            resolved = self._resolver.resolve(cmd)
            meta = resolved.definition.meta
            handler = resolved.definition.handler

            # Check if command is dangerous and requires confirmation
            if meta.dangerous and not self._should_skip_confirmation():
                confirmed = self._executor.confirm(
                    meta.confirm_msg or f"Execute dangerous command '{meta.short}'?",
                    double_confirm=meta.security_level == SecurityLevel.DESTRUCTIVE,
                )
                if not confirmed:
                    return 1, "Cancelled"

            # Execute handler
            exit_code, output = _execute_handler(
                handler, args, self._executor, self.execute
            )
            if exit_code == 0:
                record_command_use(resolved.resolved)
            return exit_code, output

        except ResolverError as e:
            suggestions = self._resolver.suggest(cmd)
            if suggestions:
                return 1, f"Error: {e}. Did you mean: {', '.join(suggestions)}?"
            return 1, f"Error: {e}"
        except SecurityError as e:
            return 1, f"Security error: {e}"
        except Exception as e:
            return 1, f"Error executing command: {e}"

    def preview(self, cmd: str, args: list[str] | None = None) -> tuple[int, str]:
        """Resolve and format a command without executing it.

        Args:
            cmd: Command name (may include aliases)
            args: Command arguments

        Returns:
            Tuple of (exit_code, formatted_command_string or error_message)
        """
        args = args or []

        # Check for override first
        if override := self._config.get_override(cmd):
            full_cmd = f"{override} {' '.join(args)}" if args else override
            return 0, full_cmd

        try:
            resolved = self._resolver.resolve(cmd)
            handler = resolved.definition.handler

            if isinstance(handler, ScriptConfig):
                steps_preview = " | ".join(handler.steps[:3])
                if len(handler.steps) > 3:
                    steps_preview += " | ..."
                return 0, f"script: {steps_preview}"

            if isinstance(handler, str):
                full_cmd = f"{handler} {' '.join(args)}" if args else handler
                return 0, full_cmd

            if callable(handler):
                try:
                    result = handler(args)
                    if isinstance(result, str):
                        return 0, result
                    return 0, str(result)
                except Exception as exc:
                    return 1, f"Preview error in handler: {exc}"

            return 1, f"Unsupported handler type: {type(handler)}"

        except ResolverError as exc:
            suggestions = self._resolver.suggest(cmd)
            if suggestions:
                return 1, f"Error: {exc}. Did you mean: {', '.join(suggestions)}?"
            return 1, f"Error: {exc}"
        except Exception as exc:
            return 1, f"Error previewing command: {exc}"

    def _should_skip_confirmation(self) -> bool:
        """Check if confirmation should be skipped.

        Returns:
            True if in CI or confirmation is disabled
        """
        # Skip in CI environment
        if os.environ.get("CI"):
            return True

        # Check user config
        return not is_truthy(self._config.settings.get("confirm_dangerous", True))

    def get_help(
        self,
        category: CommandCategory | None = None,
        dangerous_only: bool = False,
    ) -> str:
        """Get formatted help text.

        Args:
            category: Optional category filter
            dangerous_only: Show only dangerous commands

        Returns:
            Formatted help string
        """
        if dangerous_only:
            commands = self._registry.get_dangerous()
            title = "@bold(@tomato(Dangerous Commands))"
        elif category:
            commands = self._registry.get_all(category)
            title = f"@bold(@sky_blue({category.value.title()} Commands))"
        else:
            commands = self._registry.get_all()
            title = "@bold(@sky_blue(All Commands))"

        if not commands:
            return f"No commands found for: {title}"

        # Sort by category declaration order, then security level, then name.
        category_order = {cat: i for i, cat in enumerate(CommandCategory)}
        security_order = {level: i for i, level in enumerate(SecurityLevel)}
        commands.sort(
            key=lambda c: (
                category_order.get(c.meta.category, 999),
                security_order.get(c.meta.security_level, 999),
                c.meta.short,
            )
        )

        # Use plain title length for separator (markup not counted)
        plain_title = (
            "Dangerous Commands"
            if dangerous_only
            else f"{category.value.title()} Commands" if category else "All Commands"
        )
        lines = [
            f"\n{title}",
            f"@sky_blue({'─' * len(plain_title)})",
            "",
        ]

        current_category = None
        for cmd_def in commands:
            meta = cmd_def.meta

            # Category header
            if meta.category != current_category and not category:
                current_category = meta.category
                lines.append(f"\n@bold(@cyan([{current_category.value.upper()}]))")

            # Command line
            prefix = ""
            if meta.is_user_defined:
                prefix = "  @green(*)"
            elif meta.dangerous:
                prefix = "  @yellow(⚠)"
            else:
                prefix = "   "

            short_padded = f"{meta.short:<12}"
            lines.append(f"{prefix} @bold({short_padded}) {meta.help}")

        lines.append("")
        return "\n".join(lines)

    def search(self, query: str) -> list[CommandDef]:
        """Search commands by query.

        Args:
            query: Search query

        Returns:
            List of matching command definitions
        """
        query = query.lower()
        results = []

        for cmd_def in self._registry.get_all():
            meta = cmd_def.meta
            searchable = f"{meta.short} {meta.help} {' '.join(meta.examples)}".lower()
            if query in searchable:
                results.append(cmd_def)

        return results

    def list_dangerous(self) -> list[CommandDef]:
        """List all dangerous commands.

        Returns:
            List of dangerous command definitions
        """
        return self._registry.get_dangerous()


# Backward compatibility exports
__all__ = [
    # Core classes
    "GitCommandNew",
    "CommandRegistry",
    "CommandResolver",
    "SecureExecutor",
    "UserCommandConfig",
    "ScriptConfig",
    # Models
    "CommandCategory",
    "SecurityLevel",
    "CommandSource",
    "CommandMeta",
    "CommandDef",
    "ResolvedCommand",
    "CompletionItem",
    "ValidationResult",
    # Exceptions
    "RegistryError",
    "ResolverError",
    "AliasCycleError",
    "SecurityError",
    # Decorators
    "command",
    "alias",
    "dangerous",
    # Utilities
    "get_registry",
    "load_user_config",
]
