# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_renderer_context.py
Description: Renderer context management using ContextVar.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ._renderer import Renderer

# Module-level ContextVar for renderer injection
# Using ContextVar instead of global variables to support nested contexts and concurrency safety
_renderer_ctx: contextvars.ContextVar[Optional["Renderer"]] = contextvars.ContextVar(
    "renderer",
    default=None,
)


class RendererNotBoundError(RuntimeError):
    """Raised when attempting to access renderer before context is set."""

    def __init__(self) -> None:
        super().__init__(
            "Renderer not bound to current context. "
            "Ensure component is rendered within AppEventLoop.run()"
        )


def get_renderer() -> Optional["Renderer"]:
    """Get the current renderer from context.

    Returns:
        The current Renderer instance, or None if not set.
    """
    return _renderer_ctx.get()


def get_renderer_strict() -> "Renderer":
    """Get the current renderer, raising if not set.

    Returns:
        The current Renderer instance.

    Raises:
        RendererNotBoundError: If renderer context is not set.
    """
    renderer = _renderer_ctx.get()
    if renderer is None:
        raise RendererNotBoundError()
    return renderer


def set_renderer(renderer: "Renderer") -> contextvars.Token:
    """Set renderer in current context.

    ContextVar automatically handles nesting: each set creates a new context
    layer without affecting the outer context's value.

    Args:
        renderer: The Renderer instance to set.

    Returns:
        Token for resetting the context.
    """
    return _renderer_ctx.set(renderer)


def reset_renderer(token: contextvars.Token) -> None:
    """Reset renderer context using token.

    Args:
        token: The token returned by set_renderer().
    """
    _renderer_ctx.reset(token)
