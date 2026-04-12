# -*- coding: utf-8 -*-
"""
Module: pigit/termui/key_echo.py
Description: Debug helper: read semantic keys and echo them via a :class:`Renderer`.
Author: Zev
Date: 2026-03-27
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from pigit.termui.input_keyboard import KeyboardInput
    from pigit.termui.render import Renderer


def run_key_echo(
    keyboard: "KeyboardInput",
    renderer: "Renderer",
    *,
    should_stop: Optional[Callable[[list[str]], bool]] = None,
    timeout: float = 0.125,
    max_ticks: Optional[int] = None,
) -> None:
    """
    Read semantic keys and print them on the renderer (debug / smoke).

    Stops when ``should_stop`` returns True, ``max_ticks`` is reached, or ``q`` / ``ctrl c``.
    """

    ticks = 0
    while True:
        keys_batch = keyboard.read_keys(timeout=timeout)
        if keys_batch:
            renderer.write(" ".join(keys_batch) + "\n")
            renderer.flush()
        if should_stop and should_stop(keys_batch):
            break
        for k in keys_batch:
            if k in ("ctrl c", "q"):
                return
        ticks += 1
        if max_ticks is not None and ticks >= max_ticks:
            return
