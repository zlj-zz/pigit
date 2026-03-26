# -*- coding: utf-8 -*-
"""
Module: pigit/termui/deprecation.py
Description: One-shot DeprecationWarning helpers for legacy ``pigit.interactive`` / ``pigit.tui``.
Author: Project Team
Date: 2026-03-26
"""

from __future__ import annotations

import warnings
from typing import Set

_warned_keys: Set[str] = set()


def warn_package_deprecated(*, key: str, message: str) -> None:
    """
    Emit ``DeprecationWarning`` at most once per process for ``key``.

    ``stacklevel=1`` points at the call site in the caller package ``__init__``.
    """

    if key in _warned_keys:
        return
    _warned_keys.add(key)
    warnings.warn(message, DeprecationWarning, stacklevel=1)
