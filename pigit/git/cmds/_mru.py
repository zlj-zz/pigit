# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_mru.py
Description: Most-recently-used command persistence for cmd picker.
Author: Zev
Date: 2026-04-14
"""

import json
import os
from pathlib import Path
from typing import Union

from ...const import CMD_MRU_PATH


def load_mru(path: Union[str, Path] = CMD_MRU_PATH) -> list[str]:
    """Load MRU command list from JSON file.

    Args:
        path: Path to MRU JSON file

    Returns:
        List of command short names in MRU order
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [str(item) for item in data if isinstance(item, str)]
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return []


def save_mru(names: list[str], path: Union[str, Path] = CMD_MRU_PATH) -> None:
    """Save MRU command list to JSON file.

    Args:
        names: List of command short names
        path: Path to MRU JSON file
    """
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    with open(path, "w", encoding="utf-8") as f:
        json.dump(names, f, indent=2)


def record_command_use(
    name: str, max_size: int = 20, path: Union[str, Path] = CMD_MRU_PATH
) -> None:
    """Record a command use in the MRU list.

    Moves the command to the front of the list and caps the size.

    Args:
        name: Command short name
        max_size: Maximum number of entries to retain
        path: Path to MRU JSON file
    """
    mru = load_mru(path)
    # Remove existing occurrence and prepend
    filtered = [n for n in mru if n != name]
    filtered.insert(0, name)
    if len(filtered) > max_size:
        filtered = filtered[:max_size]
    save_mru(filtered, path)
