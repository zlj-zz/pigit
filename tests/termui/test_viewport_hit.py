"""
Module: tests/termui/test_viewport_hit.py
Description: Viewport hit contract tests (layout build, hit_row, double-click constant).
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from pigit.termui import bind_action
from pigit.termui.component import Component
from pigit.termui.viewport_hit import (
    DOUBLE_CLICK_MS,
    ViewportLayout,
    build_viewport_layout,
    hit_row,
)
from pigit.termui.widgets.binding_browser import BindingBrowser
from pigit.termui.widgets.help_format import build_binding_browser_layout


class _Owner(Component):
    keymap_namespace = "demo"

    @bind_action("alpha", "a", desc="Do alpha")
    def do_alpha(self) -> None:
        self.hit = "alpha"

    @bind_action("beta", "b", desc="Do beta")
    def do_beta(self) -> None:
        self.hit = "beta"

    @bind_action(
        "long",
        "l",
        desc="Do something with a quite long description that wraps onto a second line",
    )
    def do_long(self) -> None:
        self.hit = "long"


def _layout(**overrides: object) -> ViewportLayout:
    owner = _Owner()
    groups = [("Panel", owner.get_executable_bindings())]
    defaults: dict[str, object] = dict(
        inner_width=40,
        content_origin=(1, 1),
        content_width=40,
        viewport_height=11,
        scroll_offset=0,
        show_cursor=True,
    )
    defaults.update(overrides)
    return build_binding_browser_layout(groups, **defaults)


def _hit(local_row: int, local_col: int = 1, **overrides: object) -> int | None:
    return hit_row(local_row, local_col, _layout(**overrides))


class TestViewportHitInvariant:
    def test_first_content_row_maps_to_selectable_zero(self) -> None:
        # Arithmetic invariant (not a real BoxFrame): content_origin rows are
        # 0-based surface coords, mouse rows are 1-based local coords, and the
        # subtraction yields the content-local 1-based row. Real bordered-frame
        # coverage lives in test_mouse.py::TestBindingBrowserPopupMouse.
        layout = build_viewport_layout(
            [0, 1, 2],
            content_origin=(1, 1),
            content_width=40,
            viewport_height=11,
            scroll_offset=0,
        )
        assert hit_row(1, 1, layout) == 0
        assert hit_row(2, 1, layout) == 1

    def test_group_header_occupies_first_content_line(self) -> None:
        # With a group header, the first content line is not selectable and
        # the second content line maps to selectable 0.
        layout = _layout()
        assert layout.content_origin == (1, 1)
        assert layout.rows[0].selectable_index is None
        assert hit_row(1, 1, layout) is None
        assert hit_row(2, 1, layout) == 0

    def test_wrap_continuation_is_not_selectable(self) -> None:
        layout = _layout(inner_width=24, content_width=24)
        wrap_index = next(
            i
            for i in range(1, len(layout.rows))
            if layout.rows[i].selectable_index is None
            and layout.rows[i - 1].selectable_index is not None
        )
        assert len(layout.rows) > wrap_index + 1
        # Continuation line (scroll_offset 0) is content-local row index + 1.
        assert hit_row(wrap_index + 1, 1, layout) is None

    def test_hit_follows_scroll_offset(self) -> None:
        layout = build_viewport_layout(
            [None, 0, 1, 2, 3, 4, 5, 6],
            content_origin=(1, 1),
            content_width=40,
            viewport_height=5,
            scroll_offset=2,
        )
        # Viewport row 1 shows render line 2, whose selectable_index is 1.
        assert hit_row(1, 1, layout) == 1
        assert hit_row(3, 1, layout) == 3
        # Beyond the viewport bottom -> no hit.
        assert hit_row(6, 1, layout) is None

    def test_click_outside_content_column_is_not_hit(self) -> None:
        assert _hit(2, local_col=0) is None
        assert _hit(2, local_col=41) is None
        assert _hit(2, local_col=1) == 0


class TestDoubleClickConstant:
    def test_double_click_constant_defined_once(self) -> None:
        # Contract value from the mouse-support plan: 400ms.
        assert DOUBLE_CLICK_MS == 400


class TestLayoutPaintSameSource:
    def test_help_format_layout_matches_browser_rebuild(self) -> None:
        owner = _Owner()
        groups = [("Panel", owner.get_executable_bindings())]
        browser = BindingBrowser(inner_width=40, inner_height=12)
        browser.resize((80, 24))
        browser.set_groups(groups)

        layout = build_binding_browser_layout(
            groups,
            inner_width=40,
            content_origin=browser._layout.content_origin,
            content_width=browser._layout.content_width,
            viewport_height=browser._layout.viewport_height,
            scroll_offset=browser._layout.scroll_offset,
            show_cursor=True,
        )
        assert layout == browser._layout

    def test_browser_click_uses_same_geometry_as_paint(self) -> None:
        browser = BindingBrowser(inner_width=40, inner_height=12)
        owner = _Owner()
        browser.resize((80, 24))
        browser.set_groups([("Panel", owner.get_executable_bindings())])
        # The layout render table and the paint line table agree 1:1.
        assert len(browser._layout.rows) == len(browser._render)
        for row, (_, sel) in zip(browser._layout.rows, browser._render):
            assert row.selectable_index == sel
