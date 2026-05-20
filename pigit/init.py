"""
Module: pigit/init.py
Description: Shell integration initialization — completion scripts and env setup.
Author: Zev
Date: 2026-05-20
"""

from __future__ import annotations

import os
import textwrap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cmdparse.parser import Parser


_Supported_Shells = {"bash", "zsh", "fish"}


def get_shell() -> str:
    """Return the name of the current login shell from ``$SHELL``."""
    try:
        return os.environ["SHELL"].rsplit("/", 1)[-1].strip()
    except KeyError:
        return ""


def _first_arg_completion(meta) -> str:
    if meta.arg_completion is None:
        return ""
    if isinstance(meta.arg_completion, list):
        return meta.arg_completion[0].value if meta.arg_completion else ""
    return meta.arg_completion.value


def _resolve_shell(shell: str) -> str:
    """Normalize *shell* and fall back to ``$SHELL`` when empty or unsupported."""
    if shell and shell != "nil":
        candidate = shell.lower().strip()
        if candidate in _Supported_Shells:
            return candidate
    detected = get_shell()
    return detected if detected in _Supported_Shells else ""


def run_shell_init(shell: str, root_parser: "Parser") -> None:
    """Generate shell completion script for *shell* and print it to stdout.

    Args:
        shell: Target shell name, or ``"nil"`` to auto-detect from ``$SHELL``.
        root_parser: The root command parser to introspect for completion data.
    """
    from .git.cmds import get_registry, register_user_commands
    from .cmdparse.completion import shell_complete

    shell = _resolve_shell(shell)
    if not shell:
        print("")
        return

    complete_vars = root_parser.to_dict()

    register_user_commands()
    registry = get_registry()

    cmd_args = complete_vars["args"]["cmd"]["args"]

    for cmd_def in registry.get_all():
        meta = cmd_def.meta
        cmd_args[meta.short] = {
            "help": meta.help,
            "args": {},
            "arg_completion": _first_arg_completion(meta),
        }

    for alias_name, target in registry.get_aliases().items():
        cmd_args[alias_name] = {
            "help": f"Alias for {target}",
            "args": {},
            "arg_completion": "",
        }

    parts: list[str] = [shell_complete(complete_vars, shell)]

    if shell in ("bash", "zsh"):
        parts.append(textwrap.dedent("""\
                # pigit repo cd helper — auto cd after picker selection
                pigit() {
                    if [[ "$1" == "repo" && "$2" == "cd" ]]; then
                        shift 2
                        local tmpfile="${TMPDIR:-/tmp}/.pigit_cd_$$"
                        trap 'rm -f "$tmpfile"' EXIT
                        command pigit repo cd "$@" --output-file="$tmpfile"
                        if [[ -f "$tmpfile" ]]; then
                            local target
                            target=$(cat "$tmpfile")
                            [[ -n "$target" && -d "$target" ]] && cd "$target"
                        fi
                        return
                    fi
                    command pigit "$@"
                }"""))
    elif shell == "fish":
        parts.append(textwrap.dedent("""\
                # pigit repo cd helper — auto cd after picker selection
                function pigit
                    if test "$argv[1]" = "repo" -a "$argv[2]" = "cd"
                        set -e argv[1]
                        set -e argv[1]
                        set tmpfile "$TMPDIR/.pigit_cd_"(fish_pid)
                        command pigit repo cd $argv --output-file="$tmpfile"
                        if test -f "$tmpfile"
                            set target (cat "$tmpfile")
                            rm -f "$tmpfile"
                            test -n "$target" -a -d "$target"; and cd "$target"
                        end
                        return
                    end
                    command pigit $argv
                end"""))

    print("\n\n".join(parts))
