"""
Module: pigit/termui/mouse.py
Description: Mouse event model and xterm SGR mouse parser.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class MouseButton(IntEnum):
    """SGR-encoded mouse button codes."""

    LEFT = 0
    MIDDLE = 1
    RIGHT = 2
    NONE = 3
    WHEEL_UP = 64
    WHEEL_DOWN = 65
    WHEEL_LEFT = 66
    WHEEL_RIGHT = 67


class MouseKind(Enum):
    """Mouse event kind, derived from the SGR final byte (``M``=press, ``m``=release)."""

    PRESS = "M"
    RELEASE = "m"


@dataclass(frozen=True)
class MouseEvent:
    """A parsed terminal mouse event.

    ``col`` and ``row`` are 1-based, matching xterm SGR coordinates and
    :class:`~pigit.termui.component.Component` ``x``/``y`` positions.
    """

    col: int
    row: int
    button: MouseButton
    kind: MouseKind
    shift: bool = False
    alt: bool = False
    ctrl: bool = False
    motion: bool = False


def parse_sgr_mouse(data: bytes) -> MouseEvent | None:
    """Parse a complete SGR mouse sequence (``\\x1b[<b;x;yM`` / ``\\x1b[<b;x;ym``).

    The caller guarantees ``data`` is a complete sequence (its length was
    already resolved by ``_csi_or_ss3_byte_count``).

    Returns:
        A MouseEvent, or ``None`` when the sequence is not SGR mouse or is a
        wheel release/motion (one wheel detent yields exactly one event).
    """
    if len(data) < 6 or not data.startswith(b"\x1b[<"):
        return None
    final = data[-1:]
    if final not in (b"M", b"m"):
        return None
    parts = data[3:-1].decode("ascii", errors="ignore").split(";")
    if len(parts) != 3:
        return None
    try:
        raw = int(parts[0])
        col = int(parts[1])
        row = int(parts[2])
    except ValueError:
        return None

    motion = bool(raw & 0x20)
    # Wheel events set bit 6 (0x40); the low two bits encode direction:
    # 0=up, 1=down, 2=left, 3=right. Decode all four so horizontal wheel
    # (66/67) is not mis-mapped to vertical.
    if raw & 0x40:
        button = MouseButton(0x40 | (raw & 0x03))
    else:
        button = MouseButton(raw & 0x03)

    kind = MouseKind.PRESS if final == b"M" else MouseKind.RELEASE

    if raw & 0x40 and (kind is MouseKind.RELEASE or motion):
        return None

    return MouseEvent(
        col=col,
        row=row,
        button=button,
        kind=kind,
        shift=bool(raw & 0x04),
        alt=bool(raw & 0x08),
        ctrl=bool(raw & 0x10),
        motion=motion,
    )
