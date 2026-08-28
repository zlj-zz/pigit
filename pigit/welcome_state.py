"""
Module: pigit/welcome_state.py
Description: Persist first-run Welcome Sheet completion in user state file.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

import logging
import os
import tomllib

from .const import STATE_FILE_PATH

_logger = logging.getLogger(__name__)


def _load_state() -> dict[str, object]:
    """Load ``STATE_FILE_PATH`` as a flat key/value map.

    Returns:
        Parsed TOML table, or an empty dict when the file is missing or unreadable.
    """
    try:
        with open(STATE_FILE_PATH, "rb") as handle:
            return dict(tomllib.load(handle))
    except FileNotFoundError:
        return {}
    except (OSError, tomllib.TOMLDecodeError):
        _logger.warning("Failed to read state file", exc_info=True)
        return {}


def _save_state(state: dict[str, object]) -> None:
    """Write boolean top-level keys back to ``STATE_FILE_PATH``."""
    directory = os.path.dirname(STATE_FILE_PATH)
    os.makedirs(directory, exist_ok=True)
    lines: list[str] = []
    for key, value in state.items():
        if not isinstance(value, bool):
            _logger.warning("Skipping non-boolean state key %r", key)
            continue
        token = "true" if value else "false"
        lines.append(f"{key} = {token}")
    with open(STATE_FILE_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
        if lines:
            handle.write("\n")


def load_welcome_seen() -> bool:
    """Return whether the user has dismissed the auto-shown Welcome Sheet.

    Returns:
        False when state is missing or unreadable.
    """
    return bool(_load_state().get("welcome_seen", False))


def save_welcome_seen() -> None:
    """Mark the Welcome Sheet as seen for automatic first-run display."""
    try:
        state = _load_state()
        state["welcome_seen"] = True
        _save_state(state)
    except OSError:
        _logger.warning("Failed to write welcome state", exc_info=True)
