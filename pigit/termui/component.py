# -*- coding: utf-8 -*-
"""
Module: pigit/termui/component.py
Description: Thin component base for future App / picker scenes.
Author: Project Team
Date: 2026-03-26
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pigit.termui.render import Renderer


class Component(ABC):
    """Optional UI building block: layout, render, and key handling."""

    @abstractmethod
    def render(self, renderer: "Renderer") -> None:
        raise NotImplementedError

    def on_key(self, key: str) -> bool:
        """
        Handle one semantic key.

        Returns:
            True if the key was consumed.
        """

        return False
