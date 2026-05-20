import pytest
from unittest.mock import MagicMock

from pigit.termui._component import Component, ComponentError
from pigit.termui.containers import TabView
from pigit.termui.widgets import ItemList, LineTextBrowser
from pigit.termui.types import ActionEventType, OverlayDispatchResult

# --- Helpers ---


class _Leaf(Component):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_help_entries(self):
        from pigit.termui._component import _default_help_entries

        return _default_help_entries(self)

    def refresh(self):
        pass

    def _render_surface(self, surface):
        pass


class MockComponent(Component):
    def __init__(self, name, id=None):
        self._name = name
        super().__init__(id=id)

    def _render_surface(self, surface):
        pass

    def resize(self, size):
        pass

    def _handle_event(self, key):
        pass


class MockTabView(TabView):
    def update(self, action: ActionEventType, **data):
        pass


# --- Component base ---


class TestComponentBase:
    def test_emit_bubbles_to_on_event(self):
        parent = _Leaf()
        child = _Leaf()
        child.parent = parent
        parent.on_event = MagicMock(return_value=True)
        child.emit(ActionEventType.goto, target="x")
        parent.on_event.assert_called_once_with(ActionEventType.goto, target="x")

    def test_emit_without_parent_logs_warning(self):
        child = _Leaf()
        child.emit(ActionEventType.goto, target="x")

    def test_notify_children(self):
        a, b = _Leaf(), _Leaf()
        parent = _Leaf(children=[a, b])
        a.parent = parent
        b.parent = parent
        a.update = MagicMock()
        b.update = MagicMock()
        parent.notify(ActionEventType.goto, target="x")
        a.update.assert_called_once_with(ActionEventType.goto, target="x")
        b.update.assert_called_once_with(ActionEventType.goto, target="x")

    def test_notify_without_children_noop(self):
        leaf = _Leaf()
        leaf.children = []
        leaf.notify(ActionEventType.goto, target="x")

    def test_resize_propagates_to_children(self):
        child = _Leaf()
        child.resize = MagicMock(wraps=child.resize)
        parent = TabView(children=[child])
        parent.resize((10, 5))
        child.resize.assert_called_once_with((10, 5))

    def test_handle_event_binding(self):
        class _Bound(_Leaf):
            BINDINGS = [("x", "on_x")]

            def on_x(self):
                self.called = True

        leaf = _Bound()
        leaf._handle_event("x")
        assert leaf.called is True

    def test_handle_event_on_key(self):
        leaf = _Leaf()
        leaf.on_key = MagicMock()
        leaf._handle_event("k")
        leaf.on_key.assert_called_once_with("k")

    def test_has_overlay_open_default(self):
        assert _Leaf().has_overlay_open() is False

    def test_try_dispatch_overlay_default(self):
        assert (
            _Leaf().try_dispatch_overlay("k") is OverlayDispatchResult.DROPPED_UNBOUND
        )

    def test_get_help_entries_derives_from_bindings(self):
        class _Bound(_Leaf):
            BINDINGS = [("x", "on_x")]

            def on_x(self):
                """Do the thing."""
                pass

        entries = _Bound().get_help_entries()
        assert any("x" == e[0] and "Do the thing." in e[1] for e in entries)


class TestTabView:
    def test_duplicate_component_name_allowed(self):
        a = MockComponent("dup")
        b = MockComponent("dup")
        assert a._name == "dup"
        assert b._name == "dup"

    def test_container_key_routing(self):
        received: list = []

        class RecordingChild(Component):
            def __init__(self, label: str) -> None:
                self._label = label
                super().__init__(id=label)

            def _handle_event(self, key: str) -> None:
                received.append((self._label, key))

            def _render_surface(self, surface) -> None:
                pass

            def resize(self, size) -> None:
                pass

        class RoutingTabView(TabView):
            def update(self, action: ActionEventType, **data) -> None:
                pass

        main = RecordingChild("main")
        secondary = RecordingChild("secondary")

        tv = RoutingTabView(children=[main, secondary], start="main")

        # route_to switches to secondary
        tv.route_to("secondary")
        assert secondary.is_activated() is True

        # key "k" delegates to active child
        received.clear()
        tv._handle_event("k")
        assert received == [("secondary", "k")]

    @pytest.mark.parametrize(
        "start_idx, switch_target_idx, expected_active_idx",
        [
            (0, None, 0),  # Happy path: default start
            (1, None, 1),  # Happy path: specified start
            (0, 1, 1),  # Edge case: switch after init
        ],
        ids=["default-start", "specified-start", "switch-after-init"],
    )
    def test_tab_view_init_and_switch(
        self, start_idx, switch_target_idx, expected_active_idx
    ):
        main = MockComponent("main", id="main")
        secondary = MockComponent("secondary", id="secondary")
        children = [main, secondary]
        start_id = children[start_idx].id

        tab_view = MockTabView(children=children, start=start_id)
        if switch_target_idx is not None:
            tab_view.route_to(children[switch_target_idx].id)

        assert children[
            expected_active_idx
        ].is_activated(), f"child[{expected_active_idx}] should be activated"

    @pytest.mark.parametrize(
        "action, data",
        [
            ("unsupported", {}),  # unsupported action logs warning
        ],
        ids=["unsupported-action"],
    )
    def test_tab_view_accept_logs_warning(self, action, data, caplog):
        tab_view = MockTabView(children=[MockComponent("main")])
        with caplog.at_level("WARNING"):
            tab_view.accept(action, **data)
        assert "unsupported" in caplog.text or "not found" in caplog.text


class MockLineTextBrowser(LineTextBrowser):
    pass


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
        # Act
        browser = MockLineTextBrowser(x, y, size, content)

        # Assert
        assert browser.x == expected_position[0]
        assert browser.y == expected_position[1]
        if content:
            from pigit.termui._surface import Surface

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
        mocker.patch.object(browser, "refresh")

        # Act
        browser.resize(new_size)

        # Assert
        assert browser._size == expected_size
        browser.refresh.assert_called_once()

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

    def test_render_no_content(self):
        from pigit.termui._surface import Surface

        browser = MockLineTextBrowser(size=(10, 2))
        s = Surface(10, 2)
        browser._render_surface(s)

    def test_scroll_down_no_content(self):
        browser = MockLineTextBrowser(size=(10, 2))
        browser.scroll_down(1)
        assert browser._i == 0


class TestItemListFilter:
    def test_set_source_content(self):
        sel = MockItemList()
        sel.set_source_content(["x", "y"])
        assert sel.content == ["x", "y"]
        assert sel._source_content == ["x", "y"]

    def test_set_filter_basic(self):
        sel = MockItemList()
        sel.set_source_content(["apple", "banana", "apricot"])
        sel.set_filter("ap")
        assert sel.content == ["apple", "apricot"]
        assert sel._visible_to_source == [0, 2]

    def test_set_filter_empty_needle_clears(self):
        sel = MockItemList()
        sel.set_source_content(["apple", "banana"])
        sel.set_filter("ap")
        assert sel.content == ["apple"]
        sel.set_filter("")
        assert sel.content == ["apple", "banana"]

    def test_set_filter_custom_fn(self):
        sel = MockItemList()
        sel.set_source_content(["A", "B", "C"])
        sel.set_filter("a", fn=lambda row, n: row.lower() == n.lower())
        assert sel.content == ["A"]

    def test_set_filter_no_match(self):
        sel = MockItemList()
        sel.set_source_content(["apple", "banana"])
        sel.set_filter("zzz")
        assert sel.content == []
        assert sel.curr_no == 0

    def test_set_filter_idempotent(self):
        sel = MockItemList()
        sel.set_source_content(["apple", "banana"])
        sel.set_filter("ap")
        sel.set_filter("ap")
        assert sel.content == ["apple"]

    def test_source_index(self):
        sel = MockItemList()
        sel.set_source_content(["apple", "banana", "apricot"])
        sel.set_filter("ap")
        sel.curr_no = 1
        assert sel.source_index == 2

    def test_source_index_empty_visible(self):
        sel = MockItemList()
        sel.set_source_content([])
        assert sel.source_index == 0

    def test_visible_to_source(self):
        sel = MockItemList()
        sel.set_source_content(["a", "b", "c"])
        sel.set_filter("b")
        assert sel.visible_to_source(0) == 1

    def test_visible_to_source_out_of_bounds(self):
        sel = MockItemList()
        sel.set_source_content(["a", "b", "c"])
        assert sel.visible_to_source(-1) == -1
        assert sel.visible_to_source(10) == 10

    def test_visible_to_source_no_mapping(self):
        sel = MockItemList()
        sel.set_source_content(["a", "b"])
        assert sel.visible_to_source(0) == 0


class TestItemListMultiRow:
    def test_set_item_starts(self):
        sel = MockItemList()
        sel.set_source_content(["a", "b", "c"])
        sel.set_item_starts([0, 2, 4])
        assert sel._item_starts == [0, 2, 4]

    def test_set_item_starts_clamps_cursor(self):
        sel = MockItemList()
        sel.set_source_content(["a", "b"])
        sel.curr_no = 5
        sel.set_item_starts([0, 1])
        assert sel.curr_no == 1

    def test_set_item_starts_none_reverts(self):
        sel = MockItemList()
        sel.set_source_content(["a", "b"])
        sel.set_item_starts([0, 1])
        sel.set_item_starts(None)
        assert sel._item_starts is None

    def test_cursor_row_single_mode(self):
        sel = MockItemList()
        sel.set_source_content(["a", "b", "c"])
        sel.curr_no = 2
        assert sel.cursor_row() == 2

    def test_cursor_row_multi_mode(self):
        sel = MockItemList()
        sel.set_source_content(["a", "b", "c"])
        sel.set_item_starts([0, 3, 5])
        sel.curr_no = 1
        assert sel.cursor_row() == 3

    def test_row_to_item_single_mode(self):
        sel = MockItemList()
        sel.set_source_content(["a", "b"])
        assert sel.row_to_item(1) == (1, 0)

    def test_row_to_item_multi_mode(self):
        sel = MockItemList()
        sel.set_source_content(["a", "b", "c"])
        sel.set_item_starts([0, 3, 5])
        assert sel.row_to_item(4) == (1, 1)
        assert sel.row_to_item(5) == (2, 0)


class TestItemListSkipIndices:
    def test_next_skips_separator(self):
        sel = MockItemList()
        sel.set_source_content(["a", "---", "b"])
        sel.set_skip_indices({1})
        sel.curr_no = 0
        sel.next()
        assert sel.curr_no == 2

    def test_previous_skips_separator(self):
        sel = MockItemList()
        sel.set_source_content(["a", "---", "b"])
        sel.set_skip_indices({1})
        sel.curr_no = 2
        sel.previous()
        assert sel.curr_no == 0

    def test_next_with_multi_row(self):
        sel = MockItemList()
        sel.set_source_content(["a", "b", "c"])
        sel.set_item_starts([0, 1, 2])
        sel.set_skip_indices({1})
        sel.curr_no = 0
        sel.next()
        assert sel.curr_no == 2

    def test_previous_with_multi_row(self):
        sel = MockItemList()
        sel.set_source_content(["a", "b", "c"])
        sel.set_item_starts([0, 1, 2])
        sel.set_skip_indices({1})
        sel.curr_no = 2
        sel.previous()
        assert sel.curr_no == 0


class TestItemListDrawHelpers:
    def test_draw_right_aligned_draws_when_fits(self):
        from pigit.termui._surface import Surface

        sel = MockItemList(size=(20, 1))
        surface = Surface(20, 1)
        result = sel._draw_right_aligned(surface, 0, "ok", fg=(255, 255, 255))
        assert result is True
        # "ok" should appear near the right edge
        row_text = "".join(c.char for c in surface._rows[0])
        assert "ok" in row_text

    def test_draw_right_aligned_skips_when_too_wide(self):
        from pigit.termui._surface import Surface

        sel = MockItemList(size=(5, 1))
        surface = Surface(5, 1)
        result = sel._draw_right_aligned(
            surface, 0, "very_long_text", fg=(255, 255, 255)
        )
        assert result is False

    def test_draw_row_layout_with_row_bg(self):
        from pigit.termui._surface import Surface
        from pigit.termui._segment import Segment

        sel = MockItemList(size=(10, 1))
        surface = Surface(10, 1)
        left = [Segment("L", bg=(1, 2, 3))]
        main = [Segment("main")]
        right = []
        sel._draw_row_layout(surface, 0, left, main, right)
        # Row should have been pre-filled with spaces due to row_bg
        assert any(c.bg == (1, 2, 3) for c in surface._rows[0])


class MockItemList(ItemList):
    def refresh(self):
        pass


class TestItemList:
    def test_ItemList_init_error(self):
        class BadSelector(ItemList):
            CURSOR = "**"

        with pytest.raises(ComponentError):
            BadSelector()

    # Test initialization of ItemList
    @pytest.mark.parametrize(
        "x, y, size, content",
        [
            (2, 2, (10, 5), ["Item 1", "Item 2"]),
            (0, 0, (5, 5), []),
        ],
    )
    def test_ItemList_init(self, x, y, size, content):
        # Arrange
        MockItemList.CURSOR = "*"

        # Act
        selector = MockItemList(x=x, y=y, size=size, content=content)

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
    def test_ItemList_resize(self, initial_size, new_size):
        selector = MockItemList(size=initial_size)

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
    def test_ItemList_next(self, content, initial_pos, step, expected_pos):
        selector = MockItemList(content=content)
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
    def test_ItemList_previous(self, content, initial_pos, step, expected_pos):
        selector = MockItemList(content=content)
        selector.curr_no = initial_pos

        selector.previous(step=step)
        assert selector.curr_no == expected_pos


class TestItemListLazyLoad:
    def test_inactive_resize_skips_fresh_shows_placeholder(self):

        class DemoPanel(ItemList):
            CURSOR = ">"
            fresh_calls = 0

            def refresh(self):
                DemoPanel.fresh_calls += 1
                self.set_content(["ready"])

        p = DemoPanel(size=(12, 4), lazy_load=True)
        p.deactivate()
        p.resize((12, 4))
        assert DemoPanel.fresh_calls == 0
        assert p.content == ["Loading..."]

        p.activate()
        p.resize((12, 4))
        assert DemoPanel.fresh_calls == 1
        assert p.content == ["ready"]

    def test_inactive_after_load_keeps_content_on_resize(self):

        class DemoPanel2(ItemList):
            CURSOR = ">"
            fresh_calls = 0

            def refresh(self):
                DemoPanel2.fresh_calls += 1
                self.set_content(["a", "b"])

        p = DemoPanel2(size=(12, 4), lazy_load=True)
        p.activate()
        p.resize((12, 4))
        assert DemoPanel2.fresh_calls == 1
        p.deactivate()
        p.resize((20, 10))
        assert DemoPanel2.fresh_calls == 1
        assert p.content == ["a", "b"]
