# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/__init__.py
Description: cmd_new command system - unified exports and main processor.
Author: Zev
Date: 2026-04-10
"""

import os
import string

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
from . import rebase

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


def register_user_commands(
    registry: Optional[CommandRegistry] = None,
    config: Optional[UserCommandConfig] = None,
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


# Constants
SHELL_COMMAND_PREFIX = "!:"


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
        register_user_commands(self._registry, self._config)

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
        - Environment variables set via export in shell commands are preserved
          for subsequent steps

        Args:
            script: ScriptConfig instance
            args: Script arguments

        Returns:
            Tuple of (exit_code, output)
        """
        import subprocess

        outputs = []
        script_env = os.environ.copy()

        for step in script.steps:
            expanded_step = self._expand_script_vars(step, args, script_env)

            if expanded_step.startswith(SHELL_COMMAND_PREFIX):
                shell_cmd = expanded_step[len(SHELL_COMMAND_PREFIX) :].strip()
                try:
                    # Run command in subshell and capture env changes
                    result = subprocess.run(
                        f"{{ {shell_cmd}; }} && env -0",
                        shell=True,
                        capture_output=True,
                        text=True,
                        env=script_env,
                    )

                    if result.returncode != 0:
                        if result.stderr:
                            outputs.append(result.stderr)
                        return self._script_error(step, result.returncode, outputs)

                    # Parse env output and extract non-env output
                    output_lines = self._parse_env_output(result.stdout, script_env)
                    if output_lines:
                        outputs.append("\n".join(output_lines))

                except subprocess.SubprocessError as e:
                    return 1, f"Script failed at step '{step}' with error: {e}"
            else:
                parts = expanded_step.split()
                if not parts:
                    continue

                step_cmd = parts[0]
                step_args = parts[1:]

                exit_code, output = self.execute(step_cmd, step_args)
                if output:
                    outputs.append(output)

                if exit_code != 0:
                    return self._script_error(step, exit_code, outputs)

        return 0, "\n".join(outputs)

    def _parse_env_output(self, stdout: str, script_env: dict) -> list[str]:
        """Parse env -0 output, updating script_env and returning non-env lines.

        The format is: [command_output]\n[VAR=value\x00]+
        Command output (if any) appears before the first env var and has no '='.
        But echo adds \n, so we need to handle: "output\nVAR=value\x00..."

        Args:
            stdout: Output from env -0 command
            script_env: Environment dict to update with new variables

        Returns:
            List of non-environment variable output lines
        """
        lines = stdout.rstrip("\x00").split("\x00")
        output_lines = []

        for line in lines:
            if "=" not in line:
                # Lines without '=' are actual command output
                if line:
                    output_lines.append(line)
                continue

            # This line looks like VAR=value, but could be "cmd_output\nVAR=value"
            # if the command output ended with newline. Split by first '=' and check.
            key, _, value = line.partition("=")

            # If key contains newline, the part after last newline is the real key,
            # and everything before (including the newline) is command output
            if "\n" in key:
                parts = key.rsplit("\n", 1)
                cmd_output = parts[0]
                real_key = parts[1]
                if cmd_output:
                    output_lines.append(cmd_output)
                key = real_key
                # Now check if this env var is new/changed
                orig_value = os.environ.get(key)
                if orig_value is None or orig_value != value:
                    script_env[key] = value
            else:
                # Normal env var line
                orig_value = os.environ.get(key)
                if orig_value is None or orig_value != value:
                    script_env[key] = value

        return output_lines

    def _script_error(
        self, step: str, exit_code: int, outputs: list[str]
    ) -> tuple[int, str]:
        """Build error message for script failure.

        Args:
            step: Failed step
            exit_code: Return code
            outputs: Collected outputs so far

        Returns:
            Error tuple (exit_code, message)
        """
        return (
            exit_code,
            f"Script failed at step '{step}' with return code {exit_code}:\n"
            + "\n".join(outputs),
        )

    def _expand_script_vars(self, step: str, args: list[str], script_env: dict) -> str:
        """Expand variables in script step.

        Supports:
        - $1, $2, ... - positional arguments
        - $* - all arguments
        - $VAR, ${VAR} - environment variables from script_env

        Args:
            step: Script step with possible variables
            args: Positional arguments to substitute
            script_env: Environment variables dictionary

        Returns:
            Expanded step
        """
        # Build combined mapping for string.Template
        mapping = dict(script_env)
        for i, arg in enumerate(args, 1):
            mapping[str(i)] = arg
        mapping["*"] = " ".join(args) if args else ""

        return string.Template(step).safe_substitute(mapping)

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
