import pytest
from pigit.termui.components import (
    Component,
    ComponentError,
    TabView,
    GitPanelLazyResizeMixin,
    ItemSelector,
    LineTextBrowser,
)

# Mock Component to use in tests
class MockComponent(Component):
    NAME = "mock-comp"

    def __init__(self, name):
        self.NAME = name
        super().__init__()

    def _render_surface(self, surface):
        pass

    def resize(self, size):
        pass

    def _handle_event(self, key):
        pass


class MockTabView(TabView):
    NAME = "mock-tab-view"

    def update(self, action: str, **data):
        pass


class TestTabView:
    def test_duplicate_component_name_allowed(self):
        a = MockComponent("dup")
        b = MockComponent("dup")
        assert a.NAME == "dup"
        assert b.NAME == "dup"

    def test_container_key_routing_switch_first_vs_child_first(self):
        received: list = []

        class RecordingChild(Component):
            NAME = "rc"

            def __init__(self, label: str) -> None:
                self._label = label
                super().__init__()

            def _handle_event(self, key: str) -> None:
                received.append((self._label, key))

            def _render_surface(self, surface) -> None:
                pass

            def resize(self, size) -> None:
                pass

        class RoutingTabView(TabView):
            NAME = "routing-tv"

            def update(self, action: str, **data) -> None:
                pass

        def switch_tab(key: str) -> str:
            return "secondary" if key == "2" else ""

        main = RecordingChild("main")
        secondary = RecordingChild("secondary")
        children = {"main": main, "secondary": secondary}

        switch_first = RoutingTabView(
            children=dict(children),
            start_name="main",
            switch_handle=switch_tab,
            key_routing="switch_first",
        )
        received.clear()
        switch_first._handle_event("2")
        assert received == [("secondary", "2")]

        main2 = RecordingChild("main")
        sec2 = RecordingChild("secondary")
        child_first = RoutingTabView(
            children={"main": main2, "secondary": sec2},
            start_name="main",
            switch_handle=switch_tab,
            key_routing="child_first",
        )
        received.clear()
        child_first._handle_event("2")
        assert received == [("main", "2")]

    @pytest.mark.parametrize(
        "start_name, switch_key, expected_active",
        [
            ("main", None, "main"),  # Happy path: default start_name
            ("secondary", None, "secondary"),  # Happy path: specified start_name
            ("main", "secondary", "secondary"),  # Edge case: switch child after init
        ],
        ids=["default-start", "specified-start", "switch-after-init"],
    )
    def test_tab_view_init_and_switch(self, start_name, switch_key, expected_active):
        # Arrange
        children = {
            "main": MockComponent("main"),
            "secondary": MockComponent("secondary"),
        }

        def switch_handle(key):
            return switch_key or start_name

        # Act
        tab_view = MockTabView(
            children=children, start_name=start_name, switch_handle=switch_handle
        )
        if switch_key:
            tab_view._handle_event(switch_key)

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
    def test_tab_view_accept_errors(self, action, data, expected_exception):
        # Arrange
        children = {"main": MockComponent("main")}
        tab_view = MockTabView(children=children)

        # Act / Assert
        with pytest.raises(expected_exception):
            tab_view.accept(action, **data)


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
            (2, 3, (5, 3), ["a", "b", "c", "d"], (2, 3), ["a"]),  # ID: Test-2
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
        # Arrange
        mock_renderer = mocker.MagicMock()

        # Act
        browser = MockLineTextBrowser(x, y, size, content, renderer=mock_renderer)

        # Assert
        assert browser.x == expected_position[0]
        assert browser.y == expected_position[1]
        if content:
            from pigit.termui.surface import Surface

            # Components render at local (0,0) coordinates into the surface.
            s = Surface(size[0], size[1])
            browser._render_surface(s)
            for idx, expected in enumerate(expected_content):
                assert expected in s.lines()[idx]

    @pytest.mark.parametrize(
        "initial_size, new_size, expected_size",
        [
            ((10, 2), (5, 3), (5, 3)),  # ID: Test-4
            ((5, 1), (10, 5), (10, 5)),  # ID: Test-5
        ],
    )
    def test_resize(self, mocker, initial_size, new_size, expected_size):
        # Arrange
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
        browser = MockLineTextBrowser(content=content, size=[0, 1])
        browser._i = initial_index

        # Act
        browser.scroll_down(scroll_lines)

        # Assert
        assert browser._i == expected_index

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
        browser = MockLineTextBrowser(content=content)
        browser._i = initial_index

        # Act
        browser.scroll_up(scroll_lines)

        # Assert
        assert browser._i == expected_index


class MockItemSelector(ItemSelector):
    NAME = "test-item-selector"

    def fresh(self):
        pass


class TestItemSelector:
    def test_ItemSelector_init_error(self, monkeypatch):
        monkeypatch.setattr(ItemSelector, "NAME", "**")
        monkeypatch.setattr(ItemSelector, "CURSOR", "**")

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
        selector = MockItemSelector(content=content)
        selector.curr_no = initial_pos

        selector.forward(step=step)
        assert selector.curr_no == expected_pos


class TestGitPanelLazyResizeMixin:
    def test_inactive_resize_skips_fresh_shows_placeholder(self):

        class DemoPanel(GitPanelLazyResizeMixin, ItemSelector):
            NAME = "demo_lazy_git_panel"
            CURSOR = ">"
            fresh_calls = 0

            def fresh(self):
                DemoPanel.fresh_calls += 1
                self.set_content(["ready"])

        p = DemoPanel(size=(12, 4))
        p.deactivate()
        p.resize((12, 4))
        assert DemoPanel.fresh_calls == 0
        assert p.content == ["Loading..."]

        p.activate()
        p.resize((12, 4))
        assert DemoPanel.fresh_calls == 1
        assert p.content == ["ready"]

    def test_inactive_after_load_keeps_content_on_resize(self):

        class DemoPanel2(GitPanelLazyResizeMixin, ItemSelector):
            NAME = "demo_lazy_git_panel_2"
            CURSOR = ">"
            fresh_calls = 0

            def fresh(self):
                DemoPanel2.fresh_calls += 1
                self.set_content(["a", "b"])

        p = DemoPanel2(size=(12, 4))
        p.activate()
        p.resize((12, 4))
        assert DemoPanel2.fresh_calls == 1
        p.deactivate()
        p.resize((20, 10))
        assert DemoPanel2.fresh_calls == 1
        assert p.content == ["a", "b"]


class TestNearestOverlayHost:
    def test_walks_parents_to_first_overlay_host(self) -> None:
        class OverlayHost(Component):
            NAME = "overlay_host"

            def begin_popup_session(self, popup: object) -> None:
                pass

            def end_popup_session(self) -> None:
                pass

            def fresh(self) -> None:
                raise NotImplementedError

            def _render_surface(self, surface) -> None:
                pass

        host = OverlayHost()
        mid = MockComponent("mid")
        leaf = MockComponent("leaf")
        leaf.parent = mid
        mid.parent = host
        host.parent = None

        assert leaf.nearest_overlay_host() is host

    def test_returns_none_when_no_host_in_chain(self) -> None:
        root = MockComponent("root")
        leaf = MockComponent("leaf")
        leaf.parent = root
        root.parent = None

        assert leaf.nearest_overlay_host() is None
