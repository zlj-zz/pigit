# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_utils.py
Description: Utility functions for cmd_new.
Author: Project Team
Date: 2026-04-10
"""

from typing import Union, TypeVar

from pigit.ext.utils import strtobool

T = TypeVar("T")


def is_truthy(value: Union[str, bool, None]) -> bool:
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
