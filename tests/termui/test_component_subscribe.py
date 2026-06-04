"""
Integration tests for Component.subscribe() wired through ComponentRoot.
"""

from __future__ import annotations

from pigit.termui import Component
from pigit.termui._root import ComponentRoot
from pigit.termui.event_bus import EventBus
from pigit.termui.types import ActionEventType


class _Leaf(Component):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def _handler(self, *, msg: str) -> bool:
        self.calls.append(msg)
        return True


def test_subscribe_after_mount_is_immediate() -> None:
    bus = EventBus()
    leaf = _Leaf()
    root = ComponentRoot(leaf, event_bus=bus)
    leaf.parent = root

    leaf.activate()
    leaf.subscribe(ActionEventType.selection_changed, leaf._handler)
    bus.publish(ActionEventType.selection_changed, msg="hi")

    assert leaf.calls == ["hi"]


def test_subscribe_before_mount_is_replayed() -> None:
    bus = EventBus()
    leaf = _Leaf()

    # Subscribe before mounting: queued, not yet active.
    unsub = leaf.subscribe(ActionEventType.selection_changed, leaf._handler)
    assert leaf.calls == []

    # Mount: pending subscriptions are replayed onto the bus.
    root = ComponentRoot(leaf, event_bus=bus)
    leaf.parent = root
    leaf.activate()

    bus.publish(ActionEventType.selection_changed, msg="queued")
    assert leaf.calls == ["queued"]

    unsub()
    bus.publish(ActionEventType.selection_changed, msg="after")
    assert leaf.calls == ["queued"]


class _SubscribingLeaf(Component):
    """Component that subscribes inside activate(), like AppFooter/InspectorPanel."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def _handler(self, *, msg: str) -> bool:
        self.calls.append(msg)
        return True

    def activate(self) -> None:
        super().activate()
        self.subscribe(ActionEventType.selection_changed, self._handler)


def test_activate_is_reentrant() -> None:
    bus = EventBus()
    leaf = _SubscribingLeaf()
    root = ComponentRoot(leaf, event_bus=bus)
    leaf.parent = root

    leaf.activate()
    bus.publish(ActionEventType.selection_changed, msg="a")
    assert leaf.calls == ["a"]

    # Activate again: should unsubscribe previous and re-subscribe once.
    leaf.activate()
    bus.publish(ActionEventType.selection_changed, msg="b")
    assert leaf.calls == ["a", "b"]


def test_deactivate_unsubscribes() -> None:
    bus = EventBus()
    leaf = _SubscribingLeaf()
    root = ComponentRoot(leaf, event_bus=bus)
    leaf.parent = root

    leaf.activate()
    bus.publish(ActionEventType.selection_changed, msg="hi")
    assert leaf.calls == ["hi"]

    leaf.deactivate()
    bus.publish(ActionEventType.selection_changed, msg="gone")
    assert leaf.calls == ["hi"]


def test_delayed_unsubscribe_before_mount() -> None:
    leaf = _Leaf()

    unsub = leaf.subscribe(ActionEventType.selection_changed, leaf._handler)
    unsub()  # Cancel before mount

    bus = EventBus()
    root = ComponentRoot(leaf, event_bus=bus)
    leaf.parent = root
    leaf.activate()

    bus.publish(ActionEventType.selection_changed, msg="nope")
    assert leaf.calls == []
