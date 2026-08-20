# -*- coding: utf-8 -*-
"""
Module: tests/observe/test_clock.py
Description: Unit tests for FakeClock.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pigit.observe.clock import FakeClock


def test_fake_clock_starts_and_advances():
    clock = FakeClock(start=1.0)
    assert clock.monotonic() == 1.0
    clock.advance(0.3)
    assert clock.monotonic() == 1.3
