import pytest
from pigit.tui.components import (
    _Namespace,
    Container,
    Component,
    ComponentError,
    ItemSelector,
    LineTextBrowser,
)
from pigit.tui.console import Render


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


class MockContainer(Container):
    NAME = "mock-container"

    def update(self, action: str, **data):
        pass


class TestContainer:
    @pytest.mark.parametrize(
        "start_name, switch_key, expected_active",
        [
            ("main", None, "main"),  # Happy path: default start_name
            ("secondary", None, "secondary"),  # Happy path: specified start_name
            ("main", "secondary", "secondary"),  # Edge case: switch child after init
        ],
        ids=["default-start", "specified-start", "switch-after-init"],
    )
    def test_container_init_and_switch(self, start_name, switch_key, expected_active):
        # Arrange
        _Namespace.clear()
        children = {
            "main": MockComponent("main"),
            "secondary": MockComponent("secondary"),
        }
        switch_handle = lambda key: switch_key or start_name

        # Act
        container = MockContainer(
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
    def test_container_accept_errors(self, action, data, expected_exception):
        # Arrange
        _Namespace.clear()
        children = {"main": MockComponent("main")}
        container = MockContainer(children=children)

        # Act / Assert
        with pytest.raises(expected_exception):
            container.accept(action, **data)


class MockLineTextBrowser(LineTextBrowser):
    NAME = "mock-line-text-browser"


class TestLineTextBrowser:
    @pytest.mark.parametrize(
        "x, y, size, content, expected_position, expected_content",
        [
            (
                1,
                1,
                (10, 2),
                ["line1", "line2", "line3"],
                (1, 1),
                ["line1", "line2"],
            ),  # ID: Test-1
            (2, 3, (5, 1), ["a", "b", "c", "d"], (2, 3), ["a"]),  # ID: Test-2
            (
                0,
                0,
                None,
                None,
                (0, 0),
                [],
            ),  # ID: Test-3, edge case with no size and content
        ],
    )
    def test_LineTextBrowser_init(
        self, mocker, x, y, size, content, expected_position, expected_content
    ):
        _Namespace.clear()
        # Arrange
        mocker.patch("pigit.tui.components.Render.draw")

        # Act
        browser = MockLineTextBrowser(x, y, size, content)

        # Assert
        assert browser.x == expected_position[0]
        assert browser.y == expected_position[1]
        if content:
            browser._render()
            Render.draw.assert_called_with(expected_content, *expected_position, size)

    @pytest.mark.parametrize(
        "initial_size, new_size, expected_size",
        [
            ((10, 2), (5, 3), (5, 3)),  # ID: Test-4
            ((5, 1), (10, 5), (10, 5)),  # ID: Test-5
        ],
    )
    def test_resize(self, mocker, initial_size, new_size, expected_size):
        # Arrange
        _Namespace.clear()
        browser = MockLineTextBrowser(size=initial_size)
        mocker.patch.object(browser, "fresh")

        # Act
        browser.resize(new_size)

        # Assert
        assert browser._size == expected_size
        browser.fresh.assert_called_once()

    @pytest.mark.parametrize(
        "content, initial_index, scroll_lines, expected_index",
        [
            (["line1", "line2", "line3"], 0, 1, 1),  # ID: Test-6
            (["line1", "line2", "line3"], 1, 1, 2),  # ID: Test-7
            (["line1", "line2", "line3"], 2, 1, 2),  # ID: Test-8, edge case at bottom
        ],
    )
    def test_scroll_down(
        self, mocker, content, initial_index, scroll_lines, expected_index
    ):
        # Arrange
        _Namespace.clear()
        browser = MockLineTextBrowser(content=content, size=[0, 1])
        browser._i = initial_index
        mocker.patch.object(browser, "_render")

        # Act
        browser.scroll_down(scroll_lines)

        # Assert
        assert browser._i == expected_index
        browser._render.assert_called_once()

    @pytest.mark.parametrize(
        "content, initial_index, scroll_lines, expected_index",
        [
            (["line1", "line2", "line3"], 2, 1, 1),  # ID: Test-9
            (["line1", "line2", "line3"], 1, 1, 0),  # ID: Test-10
            (["line1", "line2", "line3"], 0, 1, 0),  # ID: Test-11, edge case at top
        ],
    )
    def test_scroll_up(
        self, mocker, content, initial_index, scroll_lines, expected_index
    ):
        # Arrange
        _Namespace.clear()
        browser = MockLineTextBrowser(content=content)
        browser._i = initial_index
        mocker.patch.object(browser, "_render")

        # Act
        browser.scroll_up(scroll_lines)

        # Assert
        assert browser._i == expected_index
        browser._render.assert_called_once()


class MockItemSelector(ItemSelector):
    NAME = "test-item-selector"

    def fresh(self):
        pass


class TestItemSelector:
    def test_ItemSelector_init_error(self):
        ItemSelector.NAME = "**"
        ItemSelector.CURSOR = "**"

        with pytest.raises(ComponentError):
            ItemSelector()

    # Test initialization of ItemSelector
    @pytest.mark.parametrize(
        "x, y, size, content",
        [
            (2, 2, (10, 5), ["Item 1", "Item 2"]),
            (0, 0, (5, 5), []),
        ],
    )
    def test_ItemSelector_init(self, x, y, size, content):
        # Arrange
        _Namespace.clear()
        MockItemSelector.CURSOR = "*"

        # Act
        selector = MockItemSelector(x=x, y=y, size=size, content=content)

        # Assert
        assert selector.x == x
        assert selector.y == y
        assert selector._size == size
        if content:
            assert selector.content == content
        else:
            assert selector.content == [""]

    # Test resize method
    @pytest.mark.parametrize(
        "initial_size, new_size",
        [
            ((10, 5), (20, 10)),
            ((20, 10), (5, 2)),
        ],
        ids=["resize_larger", "resize_smaller"],
    )
    def test_ItemSelector_resize(self, initial_size, new_size):
        _Namespace.clear()
        selector = MockItemSelector(size=initial_size)

        selector.resize(new_size)
        assert selector._size == new_size

    # Test next method with various steps
    @pytest.mark.parametrize(
        "content, initial_pos, step, expected_pos",
        [
            (["Item 1", "Item 2", "Item 3"], 0, 1, 1),
            (["Item 1", "Item 2", "Item 3"], 0, 2, 2),
            (["Item 1", "Item 2", "Item 3"], 2, 1, 2),
        ],
        ids=["next_single_step", "next_multiple_steps", "next_beyond_end"],
    )
    def test_ItemSelector_next(self, content, initial_pos, step, expected_pos):
        _Namespace.clear()
        selector = MockItemSelector(content=content)
        selector.curr_no = initial_pos

        selector.next(step=step)
        assert selector.curr_no == expected_pos

    # Test forward method with various steps
    @pytest.mark.parametrize(
        "content, initial_pos, step, expected_pos",
        [
            (["Item 1", "Item 2", "Item 3"], 2, 1, 1),
            (["Item 1", "Item 2", "Item 3"], 2, 2, 0),
            (["Item 1", "Item 2", "Item 3"], 0, 1, 0),
        ],
        ids=["forward_single_step", "forward_multiple_steps", "forward_beyond_start"],
    )
    def test_ItemSelector_forward(self, content, initial_pos, step, expected_pos):
        _Namespace.clear()
        selector = MockItemSelector(content=content)
        selector.curr_no = initial_pos

        selector.forward(step=step)
        assert selector.curr_no == expected_pos
