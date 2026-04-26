# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_executor.py
Description: Command execution helpers for GitCommandNew.
Author: Zev
Date: 2026-04-15
"""

import os
import string
import subprocess
from typing import Callable, Union

from ._models import ScriptConfig
from ._registry import CommandRegistry
from ._security import SecureExecutor

SHELL_COMMAND_PREFIX = "!:"


def _execute_handler(
    handler: Union[str, Callable, ScriptConfig],
    args: list[str],
    executor: SecureExecutor,
    execute_step: Callable[[str, list[str]], tuple[int, str]],
) -> tuple[int, str]:
    """Execute a handler of any supported type.

    Args:
        handler: Handler to execute (string, callable, or ScriptConfig)
        args: Command arguments
        executor: Executor with an exec method for running shell commands.
        execute_step: Callback to execute a cmd_new step within scripts.

    Returns:
        Tuple of (exit_code, output)
    """
    if isinstance(handler, ScriptConfig):
        return _execute_script(handler, args, execute_step)
    elif isinstance(handler, str):
        full_cmd = f"{handler} {' '.join(args)}" if args else handler
        return executor.exec(full_cmd)
    elif callable(handler):
        result = handler(args)
        if isinstance(result, str):
            return executor.exec(result)
        return 0, str(result)
    else:
        raise TypeError(f"Unsupported handler type: {type(handler)}")


def _execute_override(
    handler_name: str,
    args: list[str],
    executor: SecureExecutor,
    registry: CommandRegistry,
    execute_step: Callable[[str, list[str]], tuple[int, str]],
) -> tuple[int, str]:
    """Execute override handler.

    Args:
        handler_name: Name of the override handler
        args: Command arguments
        executor: Executor with an exec method.
        registry: Command registry to resolve override names.
        execute_step: Callback to execute a cmd_new step within scripts.

    Returns:
        Tuple of (exit_code, output)
    """
    try:
        override_def = registry.get(handler_name)
        return _execute_handler(override_def.handler, args, executor, execute_step)
    except Exception:
        pass

    full_cmd = f"{handler_name} {' '.join(args)}" if args else handler_name
    return executor.exec(full_cmd)


def _execute_script(
    script: ScriptConfig,
    args: list[str],
    execute_step: Callable[[str, list[str]], tuple[int, str]],
) -> tuple[int, str]:
    """Execute a multi-step script.

    Supports:
    - Shell commands (starting with !:): executed directly via shell
    - cmd_new commands: executed through cmd_new system
    - Environment variables set via export in shell commands are preserved
      for subsequent steps

    Args:
        script: ScriptConfig instance
        args: Script arguments
        execute_step: Callback to execute a cmd_new step.

    Returns:
        Tuple of (exit_code, output)
    """
    outputs = []
    script_env = os.environ.copy()

    for step in script.steps:
        expanded_step = _expand_script_vars(step, args, script_env)

        if expanded_step.startswith(SHELL_COMMAND_PREFIX):
            shell_cmd = expanded_step[len(SHELL_COMMAND_PREFIX) :].strip()
            try:
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
                    return _script_error(step, result.returncode, outputs)

                output_lines = _parse_env_output(result.stdout, script_env)
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

            exit_code, output = execute_step(step_cmd, step_args)
            if output:
                outputs.append(output)

            if exit_code != 0:
                return _script_error(step, exit_code, outputs)

    return 0, "\n".join(outputs)


def _update_script_env(key: str, value: str, script_env: dict) -> None:
    """Update script_env if the value differs from the original.

    Args:
        key: Environment variable name.
        value: New value.
        script_env: Environment dictionary to update.
    """
    orig_value = script_env.get(key)
    if orig_value is None or orig_value != value:
        script_env[key] = value


def _parse_env_output(stdout: str, script_env: dict) -> list[str]:
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
            if line:
                output_lines.append(line)
            continue

        key, _, value = line.partition("=")

        if "\n" in key:
            parts = key.rsplit("\n", 1)
            cmd_output = parts[0]
            real_key = parts[1]
            if cmd_output:
                output_lines.append(cmd_output)
            key = real_key
            _update_script_env(key, value, script_env)
        else:
            _update_script_env(key, value, script_env)

    return output_lines


def _script_error(step: str, exit_code: int, outputs: list[str]) -> tuple[int, str]:
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


def _expand_script_vars(step: str, args: list[str], script_env: dict) -> str:
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
    result = step
    for i in range(len(args), 0, -1):
        result = result.replace(f"${i}", args[i - 1])
    result = result.replace("$*", " ".join(args) if args else "")
    mapping = dict(script_env)
    return string.Template(result).safe_substitute(mapping)
