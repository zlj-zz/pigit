"""
Module: pigit/termui/bindings.py
Description: Resolve declarative ``BINDINGS`` and ``@bind_action`` into key handlers.
Author: Zev
Date: 2026-08-20

Decorator metadata is read after the class body completes; runtime mutation of
``__dict__`` or hot-reload mixing old and new classes is unsupported (undefined).
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable, Mapping, Sequence

from .keys import display_key

BindingTarget = str | Callable[[], Any]
BindingEntry = tuple[str, BindingTarget]
BindingsList = list[BindingEntry]

_ACTION_ATTR = "_pigit_action"


class BindingError(TypeError):
    """Raised when bindings cannot be resolved at construction time."""

    def __init__(
        self,
        message: str,
        *,
        semantic_key: str | None = None,
        first_target: str | None = None,
        second_target: str | None = None,
        owner_class_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.semantic_key = semantic_key
        self.first_target = first_target
        self.second_target = second_target
        self.owner_class_name = owner_class_name


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


def _describe_target(target: BindingTarget) -> str:
    """Human-readable label for a binding target in error messages."""
    if isinstance(target, str):
        return target
    return repr(target)


def _same_resolved_handler(a: Callable[..., Any], b: Callable[..., Any]) -> bool:
    """Whether two callables count as the same binding target.

    Bound methods are compared by ``__func__``/``__self__`` because attribute
    access returns a fresh bound-method object each time.
    """
    if a is b:
        return True
    if inspect.ismethod(a) and inspect.ismethod(b):
        return a.__func__ is b.__func__ and a.__self__ is b.__self__
    if inspect.isfunction(a) and inspect.isfunction(b):
        return a is b
    return False


def resolve_key_handlers(
    owner: object,
    bindings: Sequence[BindingEntry] | None,
    action_bindings: Sequence[Binding] | None = None,
) -> dict[str, Callable[..., Any]]:
    """Build ``semantic_key -> callable`` from ``BINDINGS`` and ``@bind_action``.

    Args:
        owner: The component/application whose methods are bound.
        bindings: Declarative ``(key, target)`` pairs from ``BINDINGS``.
        action_bindings: ``@bind_action`` entries collected via
            :func:`collect_action_bindings`; effective keys honour
            :func:`resolve_action_keys`.

    Returns:
        Mapping of semantic key to bound callable.

    Raises:
        BindingError: A semantic key maps to two different callables.
    """
    result: dict[str, Callable[..., Any]] = {}
    first_target_for_key: dict[str, str] = {}

    def _register(semantic_key: str, target_label: str, fn: Callable[..., Any]) -> None:
        existing = result.get(semantic_key)
        if existing is not None:
            if _same_resolved_handler(existing, fn):
                return
            raise BindingError(
                f"Duplicate binding for semantic key {semantic_key!r}: "
                f"{first_target_for_key[semantic_key]!r} conflicts with {target_label!r}",
                semantic_key=semantic_key,
                first_target=first_target_for_key[semantic_key],
                second_target=target_label,
                owner_class_name=type(owner).__name__,
            )
        first_target_for_key[semantic_key] = target_label
        result[semantic_key] = fn

    for semantic_key, target in bindings or []:
        _register(
            semantic_key,
            _describe_target(target),
            _resolve_one_target(owner, semantic_key, target),
        )

    for binding in action_bindings or []:
        fn = getattr(owner, binding.target, None)
        if not callable(fn):
            continue
        for semantic_key in resolve_action_keys(binding):
            _register(semantic_key, binding.target, fn)

    return result


@dataclass(frozen=True)
class Binding:
    """One action binding: a stable action id mapped to default keys + help metadata.

    Collected from ``@bind_action``-decorated methods. ``desc`` and ``tip_when``
    may be callables taking the owning component (bound at resolution time).
    """

    action: str
    keys: tuple[str, ...]
    target: str = ""
    desc: str | Callable[[Any], str] | None = None
    tip: str | None = None
    tip_when: Callable[[Any], bool] | None = None
    configurable: bool = True


def bind_action(
    action: str,
    *keys: str,
    desc: str | Callable[[Any], str] | None = None,
    tip: str | None = None,
    tip_when: Callable[[Any], bool] | None = None,
    configurable: bool = True,
) -> Callable[[Any], Any]:
    """Register an action binding on a method (collected with class bindings).

    Carries a stable action id plus help metadata, enabling config remapping
    and derived help/footer display.

    Args:
        action: Stable action id (e.g. ``"checkout"``).
        *keys: Default semantic keys that trigger the action.
        desc: Full help description; a callable receives the component.
        tip: Short footer hint; ``None`` means the action is not shown in the
            compact footer.
        tip_when: Optional callable returning False to hide the footer tip
            only; help (``desc``) is always shown. Mode-only actions should
            still spell the context out in ``desc``.
        configurable: Whether the user may remap this action's keys via config.
    """

    def decorator(fn: Any) -> Any:
        setattr(
            fn, _ACTION_ATTR, (action, tuple(keys), desc, tip, tip_when, configurable)
        )
        return fn

    return decorator


def _merge_by_tip(
    groups: Sequence[Sequence[tuple[str, str]]],
    transform: Callable[[str], str],
) -> list[tuple[str, str]]:
    """Group ``(key, tip)`` rows sharing a tip, joining keys with ``/``."""
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for entries in groups:
        for key, tip in entries:
            if tip not in grouped:
                grouped[tip] = []
                order.append(tip)
            grouped[tip].append(key)
    return [("/".join(transform(k) for k in grouped[tip]), tip) for tip in order]


def merge_footer_pairs(
    entries: Sequence[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Merge ``(semantic_key, tip)`` rows that share a tip into one footer entry.

    Keys are rendered with :func:`~pigit.termui.keys.display_key` and joined
    with ``/`` (e.g. ``j/k/down/up Navigate``).
    """
    return _merge_by_tip([entries], display_key)


def join_footer_display_pairs(
    parts: Sequence[Sequence[tuple[str, str]]],
) -> list[tuple[str, str]]:
    """Merge already-displayed ``(key, tip)`` rows that share a tip."""
    return _merge_by_tip(parts, lambda key: key)


def collect_action_bindings(cls: type, namespace: str = "") -> list[Binding]:
    """Collect ``Binding`` entries from ``@bind_action`` across the MRO.

    Parent class bindings are collected before subclass bindings.

    Args:
        cls: The component class.
        namespace: Optional action namespace; prefixes each action as
            ``"{namespace}.{action}"`` so config keys are unambiguous across
            panels.
    """
    out: list[Binding] = []
    for klass in reversed(cls.__mro__[:-1]):  # exclude object
        for name, obj in klass.__dict__.items():
            meta = getattr(obj, _ACTION_ATTR, None)
            if meta is None:
                continue
            action, keys, desc, tip, tip_when, configurable = meta
            full_action = f"{namespace}.{action}" if namespace else action
            out.append(
                Binding(
                    action=full_action,
                    keys=keys,
                    target=name,
                    desc=desc,
                    tip=tip,
                    tip_when=tip_when,
                    configurable=configurable,
                )
            )
    return out


# User key overrides: action id -> replacement keys. Installed once at startup
# from the app config; empty by default (no overrides).
_key_overrides: dict[str, tuple[str, ...]] = {}


def set_key_overrides(
    overrides: Mapping[str, tuple[str, ...] | list[str] | str],
) -> None:
    """Install user key overrides (action id -> keys), replacing any prior set.

    Actions not present in ``overrides`` keep their default binding. An empty
    dict clears all overrides.
    """
    _key_overrides.clear()
    for action, keys in overrides.items():
        if isinstance(keys, str):
            keys = (keys,)
        _key_overrides[action] = tuple(keys)


def resolve_action_keys(binding: Binding) -> tuple[str, ...]:
    """Return the effective keys for a binding, honoring user overrides."""
    if not binding.configurable:
        return binding.keys
    return _key_overrides.get(binding.action, binding.keys)


def resolve_instance_bindings(
    owner: Any,
) -> tuple[list[Binding], dict[str, Callable[..., Any]]]:
    """Resolve ``@bind_action`` + ``BINDINGS`` into ``(action_bindings, key_handlers)``.

    The namespace is read from the owner's class ``keymap_namespace``.
    """
    namespace = getattr(type(owner), "keymap_namespace", "")
    action_bindings = collect_action_bindings(type(owner), namespace)
    key_handlers = resolve_key_handlers(
        owner, getattr(owner, "BINDINGS", None), action_bindings
    )
    return action_bindings, key_handlers


@dataclass(frozen=True)
class ExecutableBinding:
    """One help/browser row: display fields plus a zero-arg invoke callable.

    Distinct from ``BindingEntry`` (declarative ``BINDINGS`` key/target pairs).
    """

    keys_display: str
    desc: str
    action: str
    owner: Any
    invoke: Callable[[], Any]


def derive_executable_bindings(
    bindings: Sequence[Binding],
    owner: Any,
) -> list[ExecutableBinding]:
    """Derive executable help rows from ``@bind_action`` bindings.

    Omits bindings whose ``target`` is missing or not callable on ``owner``.
    Does not filter by ``tip_when`` (help lists all actions; handlers guard modes).
    """
    rows: list[ExecutableBinding] = []
    for binding in bindings:
        if not binding.target:
            continue
        fn = getattr(owner, binding.target, None)
        if not callable(fn):
            continue
        desc = binding.desc(owner) if callable(binding.desc) else binding.desc
        if desc is None:
            desc = binding.action
        keys_display = "/".join(display_key(k) for k in resolve_action_keys(binding))
        rows.append(
            ExecutableBinding(
                keys_display=keys_display,
                desc=str(desc),
                action=binding.action,
                owner=owner,
                invoke=fn,
            )
        )
    return rows


def derive_help_entries(
    bindings: Sequence[Binding],
    owner: Any,
) -> list[tuple[str, str]]:
    """Derive ``(keys, desc)`` help entries as a projection of executable rows."""
    return [
        (row.keys_display, row.desc)
        for row in derive_executable_bindings(bindings, owner)
    ]
