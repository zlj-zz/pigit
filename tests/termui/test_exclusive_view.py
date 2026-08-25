# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_exclusive_view.py
Description: ExclusiveView exclusive visibility contract.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from pigit.termui import Component, Surface
from pigit.termui.containers import ExclusiveView


class _Box(Component):
    def __init__(self, id: str, mark: str = "x") -> None:
        super().__init__(id=id)
        self.mark = mark
        self.mounted = 0
        self.unmounted = 0

    def mount(self) -> None:
        self.mounted += 1
        super().mount()

    def unmount(self) -> None:
        self.unmounted += 1
        super().unmount()

    def paint(self, surface: Surface) -> None:
        surface.draw_text_rgb(0, 0, self.mark)


def test_construct_does_not_activate_children():
    a = _Box("a")
    b = _Box("b")
    view = ExclusiveView([a, b], visible=a)
    assert a.mounted == 0
    assert b.mounted == 0
    assert not a.is_mounted()
    assert view.visible is a


def test_activate_mounts_all_children():
    a = _Box("a")
    b = _Box("b")
    view = ExclusiveView([a, b])
    view.mount()
    assert a.mounted == 1 and a.is_mounted()
    assert b.mounted == 1 and b.is_mounted()


def test_show_does_not_deactivate_siblings():
    a = _Box("a", "A")
    b = _Box("b", "B")
    view = ExclusiveView([a, b], visible=a)
    view.mount()
    view.show(b)
    assert view.visible is b
    assert a.unmounted == 0
    assert b.unmounted == 0
    view.show("a")
    assert view.visible is a
    assert a.unmounted == 0
    assert b.unmounted == 0


def test_paint_and_hit_only_visible():
    a = _Box("a", "A")
    b = _Box("b", "B")
    view = ExclusiveView([a, b], visible=a, id="body")
    view.resize((10, 5))
    view.mount()
    surface = Surface(10, 5)
    view.paint(surface)
    assert surface.lines()[0][0] == "A"
    view.show(b)
    view.paint(surface)
    assert surface.lines()[0][0] == "B"
    hit = view._hit_test(1, 1)
    assert hit is not None
    assert hit[0] is b


def test_show_unknown_id_leaves_visible():
    a = _Box("a")
    b = _Box("b")
    view = ExclusiveView([a, b], visible=a)
    view.mount()
    assert view.show("missing") is None
    assert view.visible is a
    assert a.unmounted == 0


def test_focus_and_presentation_child_follow_visible():
    a = _Box("a")
    b = _Box("b")
    view = ExclusiveView([a, b], visible=a)
    assert view.focus_child is a
    assert view.presentation_child is a
    view.show(b)
    assert view.focus_child is b
    assert view.presentation_child is b


def test_deactivate_unmounts_all():
    a = _Box("a")
    b = _Box("b")
    view = ExclusiveView([a, b])
    view.mount()
    view.unmount()
    assert a.unmounted == 1
    assert b.unmounted == 1
    assert not a.is_mounted()


def test_hidden_child_itemlist_skips_request_render(monkeypatch):
    from pigit.termui.widgets.option_list import OptionList

    calls = {"n": 0}

    def spy():
        calls["n"] += 1

    monkeypatch.setattr("pigit.termui.widgets.option_list.request_render", spy)
    product = OptionList(content=["a"], id="product")
    detail = _Box("detail", "D")
    view = ExclusiveView([product, detail], visible=product)
    view.mount()
    view.resize((20, 5))
    product._request_render()
    assert calls["n"] == 1
    view.show(detail)
    before = calls["n"]
    product._request_render()
    assert calls["n"] == before


def test_paint_path_follows_exclusive_visible_child():
    from pigit.termui import is_on_visible_paint_path
    from pigit.termui.containers import TabView

    a = _Box("a")
    b = _Box("b")
    view = ExclusiveView([a, b], visible=a)
    assert is_on_visible_paint_path(a)
    assert not is_on_visible_paint_path(b)
    view.show(b)
    assert is_on_visible_paint_path(b)
    assert not is_on_visible_paint_path(a)

    tab_a = _Box("ta")
    tab_b = _Box("tb")
    tabs = TabView(children=[tab_a, tab_b], start="ta")
    assert is_on_visible_paint_path(tab_a)
    assert not is_on_visible_paint_path(tab_b)
    tabs.route_to("tb")
    assert is_on_visible_paint_path(tab_b)
    assert not is_on_visible_paint_path(tab_a)


def test_show_calls_on_hide_on_previous_child():
    class _HideBox(_Box):
        def __init__(self, id: str) -> None:
            super().__init__(id)
            self.hide_count = 0

        def on_hide(self) -> None:
            self.hide_count += 1

    a = _HideBox("a")
    b = _HideBox("b")
    view = ExclusiveView([a, b], visible=a)
    view.show(b)
    assert a.hide_count == 1
    assert b.hide_count == 0
    view.show(b)
    assert a.hide_count == 1
    view.show(a)
    assert b.hide_count == 1
