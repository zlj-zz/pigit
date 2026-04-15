# -*- coding: utf-8 -*-
"""
Module: pigit/termui/overlay_kinds.py
Description: Overlay modality enums and structural protocols for the single-slot modal shell.
Author: Zev
Date: 2026-04-01
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from pigit.termui.surface import Surface


class OverlayKind(Enum):
    """Whether the single modal popup slot on the root is in use."""

    NONE = 0
    POPUP = 1


class OverlayDispatchResult(Enum):
    """
    Result of routing one semantic key while an overlay is open.

    ``HANDLED_IMPLICIT`` is used when the active shell applies modal fallback policy
    (e.g. ``?`` toggles help). Unrecognized keys return ``DROPPED_UNBOUND`` (modal swallow).
    ``CLOSED_AFTER_ERROR`` is returned when dispatch raised and the host forcibly cleared
    the overlay slot (distinct from a successful explicit binding).
    """

    HANDLED_EXPLICIT = 1
    HANDLED_IMPLICIT = 2
    DROPPED_UNBOUND = 3
    CLOSED_AFTER_ERROR = 4


class OverlaySurface(Protocol):
    """
    Modal shell that may occupy the single overlay slot on an :class:`~pigit.termui.overlay_host.OverlayHostMixin` root.

    :class:`~pigit.termui.components_overlay.Popup` and :class:`~pigit.termui.components_overlay.AlertDialog`
    satisfy this protocol structurally. Other implementations may be introduced without subclassing ``Popup``.
    """

    open: bool

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        """Route one key for this modal (shell, then child, then fallback)."""

    def hide(self) -> None:
        """Release visible state for this shell."""

    def _render_surface(self, surface: "Surface") -> None:
        """Render this shell into the given Surface when active."""

    def _render(self, size: Optional[tuple[int, int]] = None) -> None:
        """Draw this shell when active (framework calls from the host)."""
