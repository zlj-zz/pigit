# -*- coding: utf-8 -*-
"""
Module: pigit/observe/clock.py
Description: Injectable monotonic clock for debounce tests.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import time
from typing import Protocol


class MonotonicClock(Protocol):
    """Clock that returns monotonic seconds."""

    def monotonic(self) -> float:
        """Return monotonic time in seconds."""
        ...


class SystemClock:
    """Production clock backed by ``time.monotonic``."""

    def monotonic(self) -> float:
        """Return ``time.monotonic()``."""
        return time.monotonic()


class FakeClock:
    """Test clock with manual ``advance``."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def monotonic(self) -> float:
        """Return the fake current time."""
        return self._now

    def advance(self, seconds: float) -> None:
        """Advance the fake clock by ``seconds``."""
        self._now += seconds
