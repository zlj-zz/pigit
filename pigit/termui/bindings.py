# -*- coding: utf-8 -*-
"""
Module: pigit/termui/bindings.py
Description: Resolve declarative ``BINDINGS`` and ``@bind_keys`` into key handlers.
Author: Project Team
Date: 2026-03-29

Decorator metadata is read after the class body completes; runtime mutation of
``__dict__`` or hot-reload mixing old and new classes is unsupported (undefined).
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

BindingTarget = Union[str, Callable[[], Any]]
BindingEntry = Tuple[str, BindingTarget]
BindingsList = List[BindingEntry]

_PIGIT_BINDING_ATTR = "_pigit_binding_keys"


class BindingError(TypeError):
    """Raised when bindings cannot be resolved at construction time."""

    def __init__(
        self,
        message: str,
        *,
        semantic_key: Optional[str] = None,
        first_target: Optional[str] = None,
        second_target: Optional[str] = None,
        owner_class_name: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.semantic_key = semantic_key
        self.first_target = first_target
        self.second_target = second_target
        self.owner_class_name = owner_class_name


def bind_keys(*semantic_keys: str) -> Callable[[Any], Any]:
    """Register one or more semantic keys on a method (collected with class bindings)."""

    def decorator(fn: Any) -> Any:
        setattr(fn, _PIGIT_BINDING_ATTR, semantic_keys)
        return fn

    return decorator


def collect_decorator_bindings(cls: type) -> BindingsList:
    """Collect ``(key, method_name)`` from ``@bind_keys`` in class definition order."""

    out: BindingsList = []
    for name in cls.__dict__:
        obj = cls.__dict__[name]
        keys = getattr(obj, _PIGIT_BINDING_ATTR, None)
        if not keys:
            continue
        if not isinstance(keys, tuple):
            continue
        for semantic_key in keys:
            out.append((semantic_key, name))
    return out


def merge_binding_entries(
    decorator_entries: BindingsList,
    class_bindings: Optional[Sequence[BindingEntry]],
) -> BindingsList:
    """Order: decorator-expanded entries first, then ``cls.BINDINGS``."""

    merged: BindingsList = list(decorator_entries)
    if class_bindings:
        merged.extend(list(class_bindings))
    return merged


def _describe_target(target: BindingTarget) -> str:
    if isinstance(target, str):
        return target
    return repr(target)


def _same_resolved_handler(a: Callable[..., Any], b: Callable[..., Any]) -> bool:
    """Whether two callables count as one binding target (§4.5)."""

    if a is b:
        return True
    if inspect.ismethod(a) and inspect.ismethod(b):
        return a.__func__ is b.__func__ and a.__self__ is b.__self__
    if inspect.isfunction(a) and inspect.isfunction(b):
        return a is b
    return False


def _resolve_one_target(
    owner: object,
    semantic_key: str,
    target: BindingTarget,
) -> Callable[..., Any]:
    if isinstance(target, str):
        fn = getattr(owner, target, None)
        if not callable(fn):
            raise BindingError(
                f"Binding for key {semantic_key!r} targets {target!r}, "
                f"which is missing or not callable on {type(owner).__name__}",
                semantic_key=semantic_key,
                first_target=target,
                owner_class_name=type(owner).__name__,
            )
        return fn
    if callable(target):
        return target
    raise TypeError(
        f"Binding target for key {semantic_key!r} must be str or callable, "
        f"got {type(target).__name__}"
    )


def resolve_key_handlers(
    owner: object,
    bindings: Optional[Sequence[BindingEntry]],
) -> Dict[str, Callable[..., Any]]:
    """
    Build ``semantic_key -> callable`` from a declarative binding list.

    Prefer :func:`resolve_key_handlers_merged` for classes that use ``@bind_keys``.
    """

    if not bindings:
        return {}
    result: Dict[str, Callable[..., Any]] = {}
    for semantic_key, target in bindings:
        result[semantic_key] = _resolve_one_target(owner, semantic_key, target)
    return result


def resolve_key_handlers_merged(
    owner: object,
    cls: type,
    bindings: Optional[Sequence[BindingEntry]],
) -> Dict[str, Callable[..., Any]]:
    """
    Merge ``@bind_keys`` metadata with ``BINDINGS``, then resolve to callables.

    Raises:
        BindingError: Duplicate semantic key mapping to different callables.
    """

    merged = merge_binding_entries(collect_decorator_bindings(cls), bindings)
    if not merged:
        return {}
    result: Dict[str, Callable[..., Any]] = {}
    first_target_for_key: Dict[str, BindingTarget] = {}
    for semantic_key, target in merged:
        call = _resolve_one_target(owner, semantic_key, target)
        existing = result.get(semantic_key)
        if existing is not None:
            if _same_resolved_handler(existing, call):
                continue
            raise BindingError(
                f"Duplicate binding for semantic key {semantic_key!r}: "
                f"{_describe_target(first_target_for_key[semantic_key])!r} "
                f"conflicts with {_describe_target(target)!r}",
                semantic_key=semantic_key,
                first_target=_describe_target(first_target_for_key[semantic_key]),
                second_target=_describe_target(target),
                owner_class_name=cls.__name__,
            )
        first_target_for_key[semantic_key] = target
        result[semantic_key] = call
    return result


def list_bindings(owner: object, cls: type) -> BindingsList:
    """Merged binding entries (same order as :func:`resolve_key_handlers_merged`)."""

    return merge_binding_entries(
        collect_decorator_bindings(cls),
        getattr(cls, "BINDINGS", None),
    )
