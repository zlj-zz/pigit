# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_picker_adapter.py
Description: Command source adapter for cmd_new --pick functionality.
Author: Zev
Date: 2026-04-10
"""

from dataclasses import dataclass
from typing import Iterator, Optional

from pigit.cmdparse.completion.base import CompletionType

from ._registry import get_registry


@dataclass
class CmdNewEntry:
    """Command entry for picker, adapted from CommandDef.

    Attributes:
        name: Command short name (e.g., 'b.c')
        help_text: Command help description
        category: Command category (e.g., 'branch', 'commit')
        is_dangerous: Whether command is marked as dangerous
        has_args: Whether command accepts arguments
        arg_completion: Optional argument completion type
    """

    name: str
    help_text: str
    category: str
    is_dangerous: bool
    has_args: bool
    arg_completion: Optional[CompletionType] = None


def iter_cmd_new_entries() -> Iterator[CmdNewEntry]:
    """Iterate over all cmd_new commands for picker.

    Yields:
        CmdNewEntry for each registered command, sorted by name.
    """
    registry = get_registry()
    for cmd_def in sorted(registry.get_all(), key=lambda c: c.meta.short):
        meta = cmd_def.meta
        comp = meta.arg_completion
        if isinstance(comp, list) and comp:
            comp = comp[0]
        yield CmdNewEntry(
            name=meta.short,
            help_text=meta.help,
            category=meta.category.value,
            is_dangerous=meta.dangerous,
            has_args=meta.has_args,
            arg_completion=comp if isinstance(comp, CompletionType) else None,
        )
