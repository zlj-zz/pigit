# -*- coding: utf-8 -*-
"""
Module: pigit/termui/components.py
Description: Git TUI component tree; drawing uses an injected :class:`~pigit.termui.render.Renderer`.
Author: Project Team
Date: 2026-03-27
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Dict, List, Literal, Optional, Tuple

if TYPE_CHECKING:
    from pigit.termui.render import Renderer


NONE_SIZE = (0, 0)

_Log = logging.getLogger(f"PIGIT.{__name__}")
_NamespaceComp = set()  # Global attr to save component name.

ActionLiteral = Literal["goto"]


class ComponentError(Exception):
    """Error class of ~Component."""


class Component(ABC):
    NAME: str = ""
    BINDINGS: Optional[List[Tuple[str, str]]] = None

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[Tuple[int, int]] = None,
        children: Optional[Dict[str, "Component"]] = None,
        parent: Optional["Component"] = None,
        renderer: Optional["Renderer"] = None,
    ) -> None:
        assert self.NAME, "The `NAME` attribute cannot be empty."
        assert (
            self.NAME not in _NamespaceComp
        ), f"The `NAME` attribute must be unique: '{self.NAME}'."
        _NamespaceComp.add(self.NAME)

        self._activated = False  # component whether activated state.

        self.x, self.y = x, y
        self._size = size or NONE_SIZE

        self.parent = parent
        self.children = children
        self._renderer = renderer

        self._event_map = {}
        if self.BINDINGS is not None:
            for b in self.BINDINGS:
                self._event_map[b[0]] = b[1]

    def activate(self):
        self._activated = True

    def deactivate(self):
        self._activated = False

    def is_activated(self):
        """Get current activate status."""
        return self._activated

    def fresh(self):
        """Fresh content data.

        Here is do nothing. If needed, should overwritten in sub-class.
        """
        raise NotImplementedError()

    def accept(self, action: ActionLiteral, **data):
        """Process emit action of child.

        Here is do nothing. If needed, should overwritten in sub-class.
        """
        raise NotImplementedError()

    def emit(self, action: ActionLiteral, **data):
        """Emit to parent."""
        assert self.parent is not None, "Has no parent to emitting."
        self.parent.accept(action, **data)

    def update(self, action: ActionLiteral, **data):
        """Process notify action of parent.

        Here is do nothing. If needed, should overwritten in sub-class.
        """
        raise NotImplementedError()

    def notify(self, action: ActionLiteral, **data):
        """Notify all children."""
        assert (
            self.children is not None
        ), f"Has no children to notifying; {self.__class__}."
        for child in self.children.values():
            child.update(action, **data)

    def resize(self, size: Tuple[int, int]):
        """Response to the resize event.

        Re-set the size of component. And refresh the content.
        If has children, let children process resize.
        """
        self._size = size
        self.fresh()

        # if has no children, None or {}
        if not self.children:
            return

        # let children process resize.
        for child in self.children.values():
            child.resize(size)

    @abstractmethod
    def _render(self, size: Optional[Tuple[int, int]] = None):
        """Render the component, overwritten in sub-class.

        Here is do nothing. If needed, should overwritten in sub-class.
        """

    def _handle_event(self, key: str):
        """Event process handle function.

        If want to custom handle, instance function `on_key(str)` in sub-class.
        Or instance attribute `BINDINGS` in sub-class. Support effectiveness both.
        """
        tg_name = self._event_map.get(key)
        if tg_name is not None:
            tg_fn = getattr(self, tg_name, None)
            if tg_fn is not None and callable(tg_fn):
                tg_fn()

        on_key = getattr(self, "on_key", None)
        if on_key is not None and callable(on_key):
            on_key(key)


class Container(Component):
    """Multiple components are stacked, only the activated sub-component can be rendered."""

    def __init__(
        self,
        children: Dict[str, "Component"],
        x: int = 1,
        y: int = 1,
        size: Optional[Tuple[int, int]] = None,
        start_name: Optional[str] = None,
        switch_handle: Optional[Callable[[str], str]] = None,
        renderer: Optional["Renderer"] = None,
    ) -> None:
        super().__init__(x, y, size, renderer=renderer)

        self.children = children
        for child in children.values():
            child.parent = self

        self.switch_handle = switch_handle

        self.name = start_name or "main"
        if self.name not in children:
            raise ComponentError(
                "Please set the name, or has a component key is 'main'."
            )

        children[self.name].activate()

    def fresh(self):
        pass  # do nothing

    def accept(self, action: ActionLiteral, **data):
        # sourcery skip: remove-unnecessary-else, swap-if-else-branches
        if action == "goto" and (name := data.get("target")) is not None:
            if child := self.switch_child(name):  # switch and fetch next child.
                child.update(action, **data)
            else:
                _Log.warning(f"Not found child: {name}.")
        else:
            raise ComponentError("Not support action of ~Container.")

    def _render(self, size: Optional[Tuple[int, int]] = None):
        """Only render the activated child component."""
        for component in self.children.values():
            if component.is_activated():
                component._render()

                # only allow one child activated.
                break

    def _handle_event(self, key: str):
        # The input will be transparently passed to the
        # child component for processing.
        for component in self.children.values():
            if component.is_activated():
                component._handle_event(key)

        if self.switch_handle:
            name = self.switch_handle(key)
            self.switch_child(name)

    def switch_child(self, name: str) -> Optional[Component]:
        """Activate ``name`` if present, refresh it, then render.

        Calls :meth:`Component.fresh` when implemented; :exc:`NotImplementedError`
        is ignored so simple test doubles keep working. Panels using
        :class:`GitPanelLazyResizeMixin` get ``_panel_loaded`` set after a successful
        switch so lazy resize stays consistent.
        """
        child = None

        if name in self.children:
            for component in self.children.values():
                if component.is_activated():
                    component.deactivate()
            target = self.children[name]
            target.activate()
            fresh_fn = getattr(target, "fresh", None)
            if callable(fresh_fn):
                try:
                    fresh_fn()
                except NotImplementedError:
                    pass
            if hasattr(target, "_panel_loaded"):
                target._panel_loaded = True
            target._render()
            child = target

        return child


class LineTextBrowser(Component):
    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[Tuple[int, int]] = None,
        content: Optional[List[str]] = None,
        renderer: Optional["Renderer"] = None,
    ) -> None:
        super().__init__(x, y, size, renderer=renderer)

        self._content = content
        self._max_line = self._size[1]

        self._i = 0  # start display line index of content.

        self._r = [0, self._size[1]]  # display range.

    def resize(self, size: Tuple[int, int]):
        self._max_line = size[1]
        super().resize(size)

    def _render(self, size: Optional[Tuple[int, int]] = None):
        if self._content and self._renderer is not None:
            self._renderer.draw_panel(
                self._content[self._i : self._i + self._max_line],
                self.x,
                self.y,
                self._size,
            )

    def scroll_up(self, line: int = 1):
        self._i = max(self._i - line, 0)
        self._render()

    def scroll_down(self, line: int = 1):
        self._i = min(self._i + line, max(0, len(self._content) - self._max_line))
        self._render()


class ItemSelector(Component):
    CURSOR: str = ""
    # Hint for callers: materialize at most this many rows per viewport refresh when building lists.
    PAGE_SIZE: int = 100

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[Tuple[int, int]] = None,
        content: Optional[List[str]] = None,
        renderer: Optional["Renderer"] = None,
    ) -> None:
        super().__init__(x, y, size, renderer=renderer)

        if len(self.CURSOR) > 1:
            raise ComponentError("error")

        self.event_map = {}
        if self.BINDINGS is not None:
            for b in self.BINDINGS:
                self.event_map[b[0]] = b[1]

        self.content = content or [""]
        self.content_len = len(self.content) - 1

        self.curr_no = 0  # default start with 0.
        self._r_start = 0

    @property
    def visible_row_count(self) -> int:
        """Viewport height in rows (how many list lines are painted per frame)."""
        return self._size[1]

    @property
    def visible_items(self):
        """Content rows in the current scroll window (pagination / virtual window)."""
        return self.content[self._r_start : self._r_start + self.visible_row_count]

    def set_content(self, content: List[str]):
        self.content = content
        self.content_len = len(self.content) - 1

    def clear_items(self):
        self.set_content([""])

    def update(self, action: ActionLiteral, **data):
        pass

    def _render(self, size: Optional[Tuple[int, int]] = None):
        if not self.content or self._renderer is None:
            return

        dis = []
        for no, item in enumerate(self.visible_items, start=self._r_start):
            if no == self.curr_no:
                dis.append(f"{self.CURSOR}{item}")
            else:
                dis.append(f" {item}")

        self._renderer.draw_panel(dis, self.x, self.y, self._size)

    def next(self, step: int = 1):
        tmp_no = self.curr_no + step
        if tmp_no < 0 or tmp_no > self.content_len:
            return

        self.curr_no += step
        if self.curr_no >= self._r_start + self._size[1]:
            self._r_start += step

        self._render()

    def forward(self, step: int = 1):
        tmp = self.curr_no - step
        if tmp < 0 or tmp > self.content_len:
            return

        self.curr_no -= step
        if self.curr_no < self._r_start:
            self._r_start -= step

        self._render()


class GitPanelLazyResizeMixin:
    """Defer expensive :meth:`fresh` until the panel is activated.

    Inactive panels show a one-line placeholder until first shown, so startup
    ``resize`` avoids running git for every tab. Pair with a container that
    calls :meth:`fresh` when switching to the child (see ``PanelContainer`` in
    :meth:`Container.switch_child`).
    """

    _panel_loaded: bool = False

    def resize(self, size: Tuple[int, int]) -> None:
        self._size = size
        if self.is_activated():
            self.fresh()
            self._panel_loaded = True
        elif not self._panel_loaded:
            self.set_content(["Loading..."])
            self.curr_no = 0
            self._r_start = 0


class Alert(Component):
    pass
