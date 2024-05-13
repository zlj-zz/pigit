from typing import Callable, Dict, Tuple
import pytest
from pigit.tui.components import Container, Component, ComponentError, _Namespace


# Mock Component to use in tests
class MockComponent(Component):
    NAME = "mock-comp"

    def __init__(self, name):
        self.NAME = name
        super().__init__()

    def _render(self):
        pass

    def resize(self, size):
        pass

    def _handle_event(self, key):
        pass


class TestContainer(Container):
    NAME = "test-container"

    def update(self, action: str, **data):
        pass


@pytest.mark.parametrize(
    "start_name, switch_key, expected_active",
    [
        ("main", None, "main"),  # Happy path: default start_name
        ("secondary", None, "secondary"),  # Happy path: specified start_name
        ("main", "secondary", "secondary"),  # Edge case: switch child after init
    ],
    ids=["default-start", "specified-start", "switch-after-init"],
)
def test_container_init_and_switch(start_name, switch_key, expected_active):
    # Arrange
    _Namespace.clear()
    children = {"main": MockComponent("main"), "secondary": MockComponent("secondary")}
    switch_handle = lambda key: switch_key or start_name

    # Act
    container = TestContainer(
        children=children, start_name=start_name, switch_handle=switch_handle
    )
    if switch_key:
        container._handle_event(switch_key)

    # Assert
    assert children[
        expected_active
    ].is_activated(), f"{expected_active} should be activated"


@pytest.mark.parametrize(
    "action, data, expected_exception",
    [
        ("unsupported", {}, ComponentError),  # Error case: unsupported action
    ],
    ids=["unsupported-action"],
)
def test_container_accept_errors(action, data, expected_exception):
    # Arrange
    _Namespace.clear()
    children = {"main": MockComponent("main")}
    container = TestContainer(children=children)

    # Act / Assert
    with pytest.raises(expected_exception):
        container.accept(action, **data)
