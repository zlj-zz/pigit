# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_focus_presentation.py
Description: Focus/presentation protocol: resolve walks, Column Tab re-sync, overlay Tab.
Author: Zev
Date: 2026-08-17
"""

from __future__ import annotations

import pytest

from pigit.termui._component import Component, resolve_focus_leaf, resolve_presentation_leaf
from pigit.termui.containers import Column, TabView
from pigit.termui._root import ComponentRoot
from pigit.termui.types import OverlayDispatchResult
from pigit.termui.widgets.sheet import Sheet
from pigit.termui._layer import LayerKind
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx


@pytest.fixture(autouse=True)
def _runtime_context():
    """Provide a fresh RuntimeContext for protocol tests."""
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    yield
    _runtime_ctx.reset(token)


def _make_root(body: Component) -> ComponentRoot:
    """Create a ComponentRoot and bind it to the current RuntimeContext."""
    root = ComponentRoot(body)
    runtime = RuntimeContext.current()
    if runtime is not None:
        runtime.overlay_host = root
        runtime.focus_manager = root._focus_manager
    return root


class _KeyLeaf(Component):
    """Leaf that records keys and lets Tab bubble to a focus-managed Column."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.received: list[str] = []

    def handle_key(self, key: str) -> bool:
        self.received.append(key)
        return key != "tab"

    def _render_surface(self, surface) -> None:
        pass


class TestResolveFocusLeaf:
    def test_focus_index_column_resolves_to_child_not_column(self):
        """resolve_focus_leaf must not return the Column (no parent-return)."""
        a = _KeyLeaf()
        b = _KeyLeaf()
        col = Column(children=[a, b], heights=[1, 1], focus_index=0)
        assert resolve_focus_leaf(col) is a
        col.set_focus_index(1)
        assert resolve_focus_leaf(col) is b


class TestResolvePresentationLeaf:
    def test_follows_presentation_child(self):
        inner = _KeyLeaf()

        class _Shell(Component):
            @property
            def presentation_child(self) -> Component | None:
                return inner

            def _render_surface(self, surface) -> None:
                pass

        shell = _Shell()
        assert resolve_presentation_leaf(shell) is inner
        assert resolve_presentation_leaf(inner) is inner


class TestColumnTabResync:
    def test_tab_does_not_cycle_column_focus(self):
        """Tab is app policy, not Column.handle_key; focus stays on the leaf."""
        a = _KeyLeaf()
        b = _KeyLeaf()
        col = Column(children=[a, b], heights=[1, 1], focus_index=0)
        root = _make_root(col)
        root.resize((20, 4))
        fm = root._focus_manager
        assert fm.get_focus_leaf() is a

        root._handle_event("tab")
        assert fm.get_focus_leaf() is a
        assert a.received == ["tab"]

        root._handle_event("j")
        assert a.received == ["tab", "j"]
        assert b.received == []


class TestTabViewResolvesIntoColumn:
    def test_start_and_route_to_chain_resolved_leaf(self):
        a = _KeyLeaf()
        b = _KeyLeaf()
        c = _KeyLeaf()
        panel = Column(children=[a, b], heights=[1, 1], focus_index=0, id="status")
        other = Column(children=[c], heights=[1], focus_index=0, id="other")
        tab_view = TabView(children=[panel, other], start="status")
        root = _make_root(tab_view)
        root.resize((20, 4))
        fm = root._focus_manager
        assert fm.get_focus_leaf() is a

        tab_view.route_to("other")
        assert fm.get_focus_leaf() is c


class _DualHookEditor(Component):
    """CommitEditor-shaped overlay: Tab mutates focus_child, no set_focus_chain."""

    def __init__(self) -> None:
        super().__init__()
        self._a = _KeyLeaf()
        self._b = _KeyLeaf()
        self._a.parent = self
        self._b.parent = self
        self._focus_index = 0

    @property
    def focus_child(self) -> Component | None:
        return self._a if self._focus_index == 0 else self._b

    @property
    def presentation_child(self) -> Component | None:
        return None

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        if key == "tab":
            self._focus_index = 1
            return OverlayDispatchResult.HANDLED_EXPLICIT
        return OverlayDispatchResult.DROPPED_UNBOUND

    def _render_surface(self, surface) -> None:
        pass


class TestOverlayTabResolvesInnerLeaf:
    def test_sheet_tab_lands_on_new_focus_child(self):
        editor = _DualHookEditor()
        body = _KeyLeaf()
        root = _make_root(body)
        root.resize((20, 10))
        sheet = Sheet(editor, height=4)
        sheet.open = True
        root._layer_stack.push(LayerKind.SHEET, sheet)
        root._focus_manager.sync_focus_to_overlay_or_leaf()
        assert root._focus_manager.get_focus_leaf() is editor._a

        root._handle_event("tab")
        assert root._focus_manager.get_focus_leaf() is editor._b


class TestCommitEditorHooks:
    def test_focus_on_input_presentation_is_self(self):
        from unittest.mock import MagicMock

        from pigit.app_commit_editor import CommitEditor

        editor = CommitEditor(
            vm=MagicMock(),
            staged_files=[],
            on_submit=lambda _msg: None,
            on_cancel=lambda: None,
        )
        assert editor.focus_child is editor._subject
        assert editor.presentation_child is None
        editor._focus_index = 1
        assert editor.focus_child is editor._body
