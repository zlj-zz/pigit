# -*- coding: utf-8 -*-
"""
Module: pigit/termui/bindings.py
Description: Resolve declarative ``BINDINGS`` tables into callable key handlers.
Author: Project Team
Date: 2026-03-29
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

BindingTarget = Union[str, Callable[[], Any]]
BindingEntry = Tuple[str, BindingTarget]
BindingsList = List[BindingEntry]


class BindingError(TypeError):
    """Raised when a ``BINDINGS`` entry cannot be resolved at construction time."""


def resolve_key_handlers(
    owner: object,
    bindings: Optional[Sequence[BindingEntry]],
) -> Dict[str, Callable[..., Any]]:
    """
    Build ``semantic_key -> callable`` from a declarative binding list.

    Args:
        owner: Object that owns string targets (resolved via ``getattr``).
        bindings: Pairs ``(semantic_key, target)``; ``target`` is a method name
            (``str``) or a no-argument callable.

    Returns:
        Mapping of semantic key to bound callable.

    Raises:
        BindingError: When a string target is missing or not callable on ``owner``.
        TypeError: When ``target`` is neither ``str`` nor callable.
    """

    if not bindings:
        return {}
    result: Dict[str, Callable[..., Any]] = {}
    for semantic_key, target in bindings:
        if isinstance(target, str):
            fn = getattr(owner, target, None)
            if not callable(fn):
                raise BindingError(
                    f"Binding for key {semantic_key!r} targets {target!r}, "
                    f"which is missing or not callable on {type(owner).__name__}"
                )
            result[semantic_key] = fn
        elif callable(target):
            result[semantic_key] = target
        else:
            raise TypeError(
                f"Binding target for key {semantic_key!r} must be str or callable, "
                f"got {type(target).__name__}"
            )
    return result
