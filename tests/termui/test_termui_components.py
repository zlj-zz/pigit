import pytest
from unittest.mock import MagicMock

from pigit.termui.component import Component, ComponentError
from pigit.termui.containers import TabView
from pigit.termui.theme import Theme, get_theme, set_theme
from pigit.termui.widgets import OptionList, TextBrowser
from pigit.termui.types import (
    EventType,
    EVT_GOTO,
    EVT_SELECTION_CHANGED,
    OverlayDispatchResult,
)

# --- Helpers ---


class _Leaf(Component):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def refresh(self):
        pass

    def paint(self, surface):
        pass


class MockComponent(Component):
    def __init__(self, name, id=None):
        self._name = name
        super().__init__(id=id)

    def paint(self, surface):
        pass

    def resize(self, size):
        pass

    def _handle_event(self, key):
        pass


class MockTabView(TabView):
    def update(self, action: EventType, **data):
        pass


# --- Component base ---


class TestComponentBase:
    def test_emit_bubbles_to_on_event(self):
        parent = _Leaf()
        child = _Leaf()
        child.parent = parent
        parent.on_event = MagicMock(return_value=True)
        child.emit(EVT_GOTO, target="x")
        parent.on_event.assert_called_once_with(EVT_GOTO, target="x")

    def test_emit_without_parent_logs_warning(self):
        child = _Leaf()
        child.emit(EVT_GOTO, target="x")

    def test_notify_children(self):
        a, b = _Leaf(), _Leaf()
        parent = _Leaf(children=[a, b])
        a.parent = parent
        b.parent = parent
        a.update = MagicMock()
        b.update = MagicMock()
        parent.notify(EVT_GOTO, target="x")
        a.update.assert_called_once_with(EVT_GOTO, target="x")
        b.update.assert_called_once_with(EVT_GOTO, target="x")

    def test_notify_without_children_noop(self):
        leaf = _Leaf()
        leaf.children = []
        leaf.notify(EVT_GOTO, target="x")

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

    def test_handle_event_handle_key(self):
        leaf = _Leaf()
        leaf.handle_key = MagicMock(return_value=True)
        leaf._handle_event("k")
        leaf.handle_key.assert_called_once_with("k")

    def test_has_overlay_open_default(self):
        assert _Leaf().has_overlay_open() is False

    def test_try_dispatch_overlay_default(self):
        assert (
            _Leaf().try_dispatch_overlay("k") is OverlayDispatchResult.DROPPED_UNBOUND
        )


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

            def paint(self, surface) -> None:
                pass

            def resize(self, size) -> None:
                pass

        class RoutingTabView(TabView):
            def update(self, action: EventType, **data) -> None:
                pass

        main = RecordingChild("main")
        secondary = RecordingChild("secondary")

        tv = RoutingTabView(children=[main, secondary], start="main")

        # route_to switches to secondary
        tv.route_to("secondary")
        assert secondary.is_mounted() is True

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
        ].is_mounted(), f"child[{expected_active_idx}] should be activated"

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


class MockTextBrowser(TextBrowser):
    pass


class TestTextBrowser:
    def test_visible_rows_caches_segment_rows(self):
        browser = TextBrowser(content=["a", "b"], size=(10, 2), bg=None)
        first = browser._visible_rows()
        second = browser._visible_rows()
        assert first is second
        assert first[0][0].text == "a"

    def test_visible_rows_rebuilds_when_theme_changes(self):
        browser = TextBrowser(content=["a"], size=(10, 1), bg=None)
        before = browser._visible_rows()
        old = get_theme()
        set_theme(Theme(fg_primary=(1, 2, 3), bg_chrome=(4, 5, 6)))
        try:
            after = browser._visible_rows()
            assert after is not before
        finally:
            set_theme(old)

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
    def test_TextBrowser_init(
        self, mocker, x, y, size, content, expected_position, expected_content
    ):
        # Act
        browser = MockTextBrowser(x, y, size, content)

        # Assert
        assert browser.x == expected_position[0]
        assert browser.y == expected_position[1]
        if content:
            from pigit.termui.surface import Surface

            # Components render at local (0,0) coordinates into the surface.
            s = Surface(size[0], size[1])
            browser.paint(s)
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
        browser = MockTextBrowser(size=initial_size)
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
        browser = MockTextBrowser(content=content, size=[0, 1])
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
        browser = MockTextBrowser(content=content)
        browser._i = initial_index

        # Act
        browser.scroll_up(scroll_lines)

        # Assert
        assert browser._i == expected_index

    def test_render_no_content(self):
        from pigit.termui.surface import Surface

        browser = MockTextBrowser(size=(10, 2))
        s = Surface(10, 2)
        browser.paint(s)

    def test_scroll_down_no_content(self):
        browser = MockTextBrowser(size=(10, 2))
        browser.scroll_down(1)
        assert browser._i == 0

    def test_render_transparent_bg_does_not_paint_cell_background(self):
        from pigit.termui.surface import Surface

        browser = MockTextBrowser(content=["hi"], size=(10, 2), bg=None)
        surface = Surface(10, 2)
        surface.draw_text_rgb(0, 0, "XXXX", bg=(9, 9, 9))
        browser.paint(surface)
        assert surface._rows[0][0].char == "h"
        assert surface._rows[0][0].bg is None
        assert surface._rows[0][2].char == "X"
        assert surface._rows[0][2].bg == (9, 9, 9)

    def test_render_segment_rows_keeps_fg(self):
        from pigit.termui.segment import Segment
        from pigit.termui.surface import Surface

        fg = (1, 2, 3)
        browser = MockTextBrowser(
            content=[[Segment("ab", fg=fg)]], size=(10, 2), bg=None
        )
        surface = Surface(10, 2)
        browser.paint(surface)
        assert surface._rows[0][0].char == "a"
        assert surface._rows[0][0].fg == fg


class TestOptionListFilter:
    def test_set_source_content(self):
        sel = MockOptionList()
        sel.set_source_content(["x", "y"])
        assert sel.content == ["x", "y"]
        assert sel._source_content == ["x", "y"]

    def test_set_filter_basic(self):
        sel = MockOptionList()
        sel.set_source_content(["apple", "banana", "apricot"])
        sel.set_filter("ap")
        assert sel.content == ["apple", "apricot"]
        assert sel._visible_to_source == [0, 2]

    def test_set_filter_empty_needle_clears(self):
        sel = MockOptionList()
        sel.set_source_content(["apple", "banana"])
        sel.set_filter("ap")
        assert sel.content == ["apple"]
        sel.set_filter("")
        assert sel.content == ["apple", "banana"]

    def test_set_filter_custom_fn(self):
        sel = MockOptionList()
        sel.set_source_content(["A", "B", "C"])
        sel.set_filter("a", fn=lambda row, n: row.lower() == n.lower())
        assert sel.content == ["A"]

    def test_set_filter_no_match(self):
        sel = MockOptionList()
        sel.set_source_content(["apple", "banana"])
        sel.set_filter("zzz")
        assert sel.content == []
        assert sel.curr_no == 0

    def test_set_filter_idempotent(self):
        sel = MockOptionList()
        sel.set_source_content(["apple", "banana"])
        sel.set_filter("ap")
        sel.set_filter("ap")
        assert sel.content == ["apple"]

    def test_source_index(self):
        sel = MockOptionList()
        sel.set_source_content(["apple", "banana", "apricot"])
        sel.set_filter("ap")
        sel.curr_no = 1
        assert sel.source_index == 2

    def test_source_index_empty_visible(self):
        sel = MockOptionList()
        sel.set_source_content([])
        assert sel.source_index == 0

    def test_visible_to_source(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "b", "c"])
        sel.set_filter("b")
        assert sel.visible_to_source(0) == 1

    def test_visible_to_source_out_of_bounds(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "b", "c"])
        assert sel.visible_to_source(-1) == -1
        assert sel.visible_to_source(10) == 10

    def test_visible_to_source_no_mapping(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "b"])
        assert sel.visible_to_source(0) == 0


class TestOptionListMultiRow:
    def test_set_item_starts(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "b", "c"])
        sel.set_item_starts([0, 2, 4])
        assert sel._item_starts == [0, 2, 4]

    def test_set_item_starts_clamps_cursor(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "b"])
        sel.curr_no = 5
        sel.set_item_starts([0, 1])
        assert sel.curr_no == 1

    def test_set_item_starts_none_reverts(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "b"])
        sel.set_item_starts([0, 1])
        sel.set_item_starts(None)
        assert sel._item_starts is None

    def test_cursor_row_single_mode(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "b", "c"])
        sel.curr_no = 2
        assert sel.cursor_row() == 2

    def test_cursor_row_multi_mode(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "b", "c"])
        sel.set_item_starts([0, 3, 5])
        sel.curr_no = 1
        assert sel.cursor_row() == 3

    def test_row_to_item_single_mode(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "b"])
        assert sel.row_to_item(1) == (1, 0)

    def test_row_to_item_multi_mode(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "b", "c"])
        sel.set_item_starts([0, 3, 5])
        assert sel.row_to_item(4) == (1, 1)
        assert sel.row_to_item(5) == (2, 0)


class TestOptionListSkipIndices:
    def test_next_skips_separator(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "---", "b"])
        sel.set_skip_indices({1})
        sel.curr_no = 0
        sel.next()
        assert sel.curr_no == 2

    def test_previous_skips_separator(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "---", "b"])
        sel.set_skip_indices({1})
        sel.curr_no = 2
        sel.previous()
        assert sel.curr_no == 0

    def test_next_with_multi_row(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "b", "c"])
        sel.set_item_starts([0, 1, 2])
        sel.set_skip_indices({1})
        sel.curr_no = 0
        sel.next()
        assert sel.curr_no == 2

    def test_previous_with_multi_row(self):
        sel = MockOptionList()
        sel.set_source_content(["a", "b", "c"])
        sel.set_item_starts([0, 1, 2])
        sel.set_skip_indices({1})
        sel.curr_no = 2
        sel.previous()
        assert sel.curr_no == 0


class TestOptionListDrawHelpers:
    def test_draw_right_aligned_draws_when_fits(self):
        from pigit.termui.surface import Surface

        sel = MockOptionList(size=(20, 1))
        surface = Surface(20, 1)
        result = sel._draw_right_aligned(surface, 0, "ok", fg=(255, 255, 255))
        assert result is True
        # "ok" should appear near the right edge
        row_text = "".join(c.char for c in surface._rows[0])
        assert "ok" in row_text

    def test_draw_right_aligned_skips_when_too_wide(self):
        from pigit.termui.surface import Surface

        sel = MockOptionList(size=(5, 1))
        surface = Surface(5, 1)
        result = sel._draw_right_aligned(
            surface, 0, "very_long_text", fg=(255, 255, 255)
        )
        assert result is False

    def test_draw_row_layout_with_row_bg(self):
        from pigit.termui.surface import Surface
        from pigit.termui.segment import Segment

        sel = MockOptionList(size=(10, 1))
        surface = Surface(10, 1)
        left = [Segment("L", bg=(1, 2, 3))]
        main = [Segment("main")]
        right = []
        sel._draw_row_layout(surface, 0, left, main, right)
        # Row should have been pre-filled with spaces due to row_bg
        assert any(c.bg == (1, 2, 3) for c in surface._rows[0])


class MockOptionList(OptionList):
    def refresh(self):
        pass


class TestOptionList:
    def test_OptionList_init_error(self):
        class BadSelector(OptionList):
            CURSOR = "**"

        with pytest.raises(ComponentError):
            BadSelector()

    # Test initialization of OptionList
    @pytest.mark.parametrize(
        "x, y, size, content",
        [
            (2, 2, (10, 5), ["Item 1", "Item 2"]),
            (0, 0, (5, 5), []),
        ],
    )
    def test_OptionList_init(self, x, y, size, content):
        # Arrange
        MockOptionList.CURSOR = "*"

        # Act
        selector = MockOptionList(x=x, y=y, size=size, content=content)

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
    def test_OptionList_resize(self, initial_size, new_size):
        selector = MockOptionList(size=initial_size)

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
    def test_OptionList_next(self, content, initial_pos, step, expected_pos):
        selector = MockOptionList(content=content)
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
    def test_OptionList_previous(self, content, initial_pos, step, expected_pos):
        selector = MockOptionList(content=content)
        selector.curr_no = initial_pos

        selector.previous(step=step)
        assert selector.curr_no == expected_pos


class TestOptionListLazyLoad:
    def test_inactive_resize_skips_fresh_shows_placeholder(self):

        class DemoPanel(OptionList):
            CURSOR = ">"
            fresh_calls = 0

            def refresh(self):
                DemoPanel.fresh_calls += 1
                self.set_content(["ready"])

        p = DemoPanel(size=(12, 4), lazy_load=True)
        p.unmount()
        p.resize((12, 4))
        assert DemoPanel.fresh_calls == 0
        assert p.content == ["Loading..."]

        p.mount()
        p.resize((12, 4))
        assert DemoPanel.fresh_calls == 1
        assert p.content == ["ready"]

    def test_inactive_after_load_keeps_content_on_resize(self):

        class DemoPanel2(OptionList):
            CURSOR = ">"
            fresh_calls = 0

            def refresh(self):
                DemoPanel2.fresh_calls += 1
                self.set_content(["a", "b"])

        p = DemoPanel2(size=(12, 4), lazy_load=True)
        p.mount()
        p.resize((12, 4))
        assert DemoPanel2.fresh_calls == 1
        p.unmount()
        p.resize((20, 10))
        assert DemoPanel2.fresh_calls == 1
        assert p.content == ["a", "b"]
