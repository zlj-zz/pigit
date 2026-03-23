# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmd_catalog.py
Description: Normalized command entries for list, search, and interactive pick.
Author: Project Team
Date: 2026-03-22
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Literal, Union

from .define import GitCommandType

Source = Literal["builtin", "extra"]


@dataclass(frozen=True)
class CommandEntry:
    """One short-command row shared by list, search, and pick."""

    name: str
    help_text: str
    command_repr: str
    belong: GitCommandType
    source: Source
    has_arguments: bool


def command_repr_value(command: Union[str, Callable, None]) -> str:
    """Stable text used for search matching (mirrors generate_help_by_key)."""
    if command is None:
        return ""
    if callable(command):
        return f"func:{getattr(command, '__name__', 'anonymous')}"
    return str(command)


def iter_command_entries(
    cmds: Dict[str, dict],
    extra_cmd_keys: frozenset[str],
) -> List[CommandEntry]:
    """Build sorted command entries with builtin vs extra source."""
    out: List[CommandEntry] = []
    for name in sorted(cmds.keys()):
        spec = cmds[name]
        belong = spec.get("belong", GitCommandType.Extra)
        if not isinstance(belong, GitCommandType):
            belong = GitCommandType.Extra
        raw = spec.get("command")
        source: Source = "extra" if name in extra_cmd_keys else "builtin"
        out.append(
            CommandEntry(
                name=name,
                help_text=(spec.get("help") or "").strip(),
                command_repr=command_repr_value(raw),
                belong=belong,
                source=source,
                has_arguments=bool(spec.get("has_arguments", False)),
            )
        )
    return out
