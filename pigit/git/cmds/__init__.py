# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/__init__.py
Description: cmd_new command system - unified exports and main processor.
Author: Project Team
Date: 2026-04-10
"""

import os

from typing import TYPE_CHECKING, Callable, Optional, Union

# Import all command modules to trigger registration
from . import branch
from . import commit
from . import index
from . import working_tree
from . import push_pull
from . import remote
from . import history
from . import merge
from . import conflict
from . import submodule
from . import settings

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


# Import for type checking
if TYPE_CHECKING:
    pass


class GitCommandNew:
    """New Git command processor running parallel to GitProxy.

    This class provides the main interface for the new command system,
    integrating registry, resolver, config, validator, and secure executor.
    """

    def __init__(
        self,
        registry: Optional[CommandRegistry] = None,
        resolver: Optional[CommandResolver] = None,
        config: Optional[UserCommandConfig] = None,
        executor: Optional[SecureExecutor] = None,
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
        self._register_user_commands()

    def _register_user_commands(self) -> None:
        """Register user-defined aliases and scripts as standard commands."""
        from ._models import CommandDef, CommandMeta, CommandCategory, CommandSource

        # Register aliases as standard commands
        for alias_name, target in self._config.aliases.items():
            try:
                # Register as alias in resolver
                self._registry.add_alias(alias_name, target)

                # Also register as a command for completion
                cmd_def = CommandDef(
                    meta=CommandMeta(
                        short=alias_name,
                        category=CommandCategory.ALIAS,
                        help=f"Alias for {target}",
                        source=CommandSource.ALIAS,
                        is_user_defined=True,
                    ),
                    handler=target,
                )
                self._registry.register(cmd_def)
            except RegistryError:
                # Skip conflicting aliases
                pass

        # Register scripts as standard commands
        for name, script in self._config.scripts.items():
            try:
                cmd_def = CommandDef(
                    meta=CommandMeta(
                        short=name,
                        category=CommandCategory(script.category),
                        help=script.help or f"User script: {name}",
                        dangerous=script.dangerous,
                        confirm_msg=script.confirm_msg,
                        examples=script.examples,
                        source=CommandSource.SCRIPT,
                        is_user_defined=True,
                    ),
                    handler=script,
                )
                self._registry.register(cmd_def)
            except RegistryError:
                # Skip conflicting scripts
                pass

    def execute(self, cmd: str, args: Optional[list[str]] = None) -> tuple[int, str]:
        """Execute a command.

        Args:
            cmd: Command name (may include aliases)
            args: Command arguments

        Returns:
            Tuple of (exit_code, output)
        """
        args = args or []

        # Check for override first
        if override := self._config.get_override(cmd):
            return self._execute_override(override, args)

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
            return self._execute_handler(handler, args)

        except ResolverError as e:
            suggestions = self._resolver.suggest(cmd)
            if suggestions:
                return 1, f"Error: {e}. Did you mean: {', '.join(suggestions)}?"
            return 1, f"Error: {e}"
        except SecurityError as e:
            return 1, f"Security error: {e}"
        except Exception as e:
            return 1, f"Error executing command: {e}"

    def _execute_handler(
        self, handler: Union[str, Callable, ScriptConfig], args: list[str]
    ) -> tuple[int, str]:
        """Execute a handler of any supported type.

        Args:
            handler: Handler to execute (string, callable, or ScriptConfig)
            args: Command arguments

        Returns:
            Tuple of (exit_code, output)
        """
        if isinstance(handler, ScriptConfig):
            return self._execute_script(handler, args)
        elif isinstance(handler, str):
            full_cmd = f"{handler} {' '.join(args)}" if args else handler
            return self._executor.exec(full_cmd)
        elif callable(handler):
            result = handler(args)
            if isinstance(result, str):
                return self._executor.exec(result)
            return 0, str(result)
        else:
            raise TypeError(f"Unsupported handler type: {type(handler)}")

    def _execute_override(self, handler_name: str, args: list[str]) -> tuple[int, str]:
        """Execute override handler.

        Args:
            handler_name: Name of the override handler
            args: Command arguments

        Returns:
            Tuple of (exit_code, output)
        """
        # Try to find handler in registry
        try:
            override_def = self._registry.get(handler_name)
            return self._execute_handler(override_def.handler, args)
        except Exception:
            pass

        # Fallback: execute as shell command
        full_cmd = f"{handler_name} {' '.join(args)}" if args else handler_name
        return self._executor.exec(full_cmd)

    def _execute_script(self, script: ScriptConfig, args: list[str]) -> tuple[int, str]:
        """Execute a multi-step script.

        Supports:
        - Shell commands (starting with !:): executed directly via shell
        - cmd_new commands: executed through cmd_new system

        Args:
            script: ScriptConfig instance
            args: Script arguments

        Returns:
            Tuple of (exit_code, output)
        """
        import subprocess
        import os

        outputs = []
        # Environment for shell commands (inherits current environment)
        script_env = os.environ.copy()

        for step in script.steps:
            # Expand positional args
            expanded_step = self._expand_positional_args(step, args)

            # Check if it's a shell command (starts with !:)
            if expanded_step.startswith("!:"):
                # Execute as shell command
                shell_cmd = expanded_step[2:].strip()  # Remove leading !:
                try:
                    result = subprocess.run(
                        shell_cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        env=script_env,
                    )
                    # stderr is captured but not returned as error for shell commands
                    # (commands like export produce no output but succeed)
                    if result.stderr:
                        outputs.append(result.stderr)
                    if result.stdout:
                        outputs.append(result.stdout)

                    if result.returncode != 0:
                        return (
                            result.returncode,
                            f"Script failed at step '{step}' with return code {result.returncode}:\n"
                            + "\n".join(outputs),
                        )
                except Exception as e:
                    return 1, f"Script failed at step '{step}' with error: {e}"
            else:
                # Parse step as cmd_new command + args
                parts = expanded_step.split()
                if not parts:
                    continue

                step_cmd = parts[0]
                step_args = parts[1:] if len(parts) > 1 else []

                # Execute the step
                exit_code, output = self.execute(step_cmd, step_args)
                if output:
                    outputs.append(output)

                if exit_code != 0:
                    return (
                        exit_code,
                        f"Script failed at step '{step}' with return code {exit_code}:\n"
                        + "\n".join(outputs),
                    )

        return 0, "\n".join(outputs)

    def _expand_positional_args(self, step: str, args: list[str]) -> str:
        """Expand positional arguments in script step.

        Supports:
        - $1, $2, ... - positional arguments
        - $* - all arguments

        Environment variables should be handled by the shell (!: prefix)
        using standard $VAR or ${VAR} syntax.

        Args:
            step: Script step with possible variables
            args: Arguments to substitute

        Returns:
            Expanded step
        """
        # Expand positional args
        for i, arg in enumerate(args, 1):
            step = step.replace(f"${i}", arg)

        # Expand $*
        if args:
            step = step.replace("$*", " ".join(args))

        return step

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
        category: Optional[CommandCategory] = None,
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
            title = "Dangerous Commands"
        elif category:
            commands = self._registry.get_all(category)
            title = f"{category.value.title()} Commands"
        else:
            commands = self._registry.get_all()
            title = "All Commands"

        if not commands:
            return f"No commands found for: {title}"

        # Sort commands by category then name
        commands.sort(key=lambda c: (c.meta.category.value, c.meta.short))

        lines = [f"\n{title}", "=" * len(title), ""]

        current_category = None
        for cmd_def in commands:
            meta = cmd_def.meta

            # Category header
            if meta.category != current_category and not category:
                current_category = meta.category
                lines.append(f"\n[{current_category.value.upper()}]")

            # Command line
            prefix = ""
            if meta.is_user_defined:
                prefix = "  📝"
            elif meta.dangerous:
                prefix = "  ⚠️"
            else:
                prefix = "     "

            lines.append(f"{prefix} {meta.short:<12} {meta.help}")

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
