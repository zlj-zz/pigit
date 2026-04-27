# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_session_context.py
Description: Session ContextVar — exposes the current TUI session for exec_external.
Author: Zev
Date: 2026-04-27
"""

from __future__ import annotations

import contextvars
import logging
import subprocess
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ._session import Session

_session_ctx: contextvars.ContextVar[Optional["Session"]] = contextvars.ContextVar(
    "termui_session", default=None
)

_logger = logging.getLogger(__name__)


def set_session(session: "Session") -> contextvars.Token:
    """Set the current TUI session in context."""
    return _session_ctx.set(session)


def reset_session(token: contextvars.Token) -> None:
    """Reset session context to previous value."""
    _session_ctx.reset(token)


def get_session() -> Optional["Session"]:
    """Get the current TUI session from context."""
    return _session_ctx.get()


def exec_external(
    cmd: list[str],
    cwd: Optional[str] = None,
) -> "subprocess.CompletedProcess[str]":
    """Suspend TUI, run an external command, then resume TUI and redraw.

    Works from anywhere inside a :class:`~pigit.termui.session.Session` context.
    """
    session = get_session()
    if session is None:
        raise RuntimeError("No active TUI session; call only inside Session context.")

    session.suspend()
    result: "subprocess.CompletedProcess[str]"
    try:
        result = subprocess.run(cmd, cwd=cwd, stdin=None, stdout=None, stderr=None)
    finally:
        try:
            session.resume()
        except Exception:
            _logger.exception("Session.resume() failed; terminal may be in bad state")
            raise
    return result
