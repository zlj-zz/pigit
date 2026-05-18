"""
Module: pigit/git/cmds/_utils.py
Description: Utility functions for cmd_new.
Author: Zev
Date: 2026-04-10
"""

from __future__ import annotations

from typing import TypeVar

from pigit.ext.utils import strtobool

T = TypeVar("T")


def is_truthy(value: str | bool | None) -> bool:
    """Check if value is truthy.

    Args:
        value: Value to check

    Returns:
        True if truthy
    """
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    try:
        return strtobool(str(value))
    except ValueError:
        return False
