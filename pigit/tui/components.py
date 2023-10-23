from abc import ABC, abstractmethod
from math import ceil
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

from pigit.ext.log import logger

from .console import Render
from .utils import get_width, plain


NONE_SIZE = (0, 0)


class ComponentError(Exception):
    """Error class of ~Component."""


class Component(ABC):
    BINDINGS: Optional[List[Tuple[str, str]]] = None

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        size: Optional[Tuple[int, int]] = None,
        children: Optional[Dict[str, "Component"]] = None,
        parent: Optional["Component"] = None,
    ) -> None:
        self._activated = False  # component whether activated state.

        self.x = x
        self.y = y
        self._size = size or (0, 0)

        self.parent = parent
        self.children = children

        self._event_map = {}
        if self.BINDINGS is not None:
            for b in self.BINDINGS:
                self._event_map[b[0]] = b[1]

    def activate(self):
        self._activated = True

    def deactivate(self):
        self._activated = False

    def is_activated(self):
        return self._activated

    def fresh(self):
        """Fresh content data."""
        raise NotImplementedError()

    def accept(self, action, **data):
        """Process emit action of child.

        Here is do nothing. If needed, should overwritten in sub-class.
        """
        raise NotImplementedError()

    def emit(self, action, **data):
        """Emit to parent."""
        assert self.parent is not None, "Has no parent to emitting."
        self.parent.accept(action, **data)

    def update(self, action, **data):
        """Process notify action of parent.

        Here is do nothing. If needed, should overwritten in sub-class.
        """
        raise NotImplementedError()

    def notify(self, action, **data):
        """Notify all children."""
        assert (
            self.children is not None
        ), f"Has no children to notifying; {self.__class__}."
        for child in self.children.values():
            child.update(action, **data)

    @abstractmethod
    def resize(self, size):
        """Response to the resize event."""

    @abstractmethod
    def _render(self, size: Optional[Tuple[int, int]] = None):
        """Render the component, overwritten in sub-class."""

    def _handle_event(self, key: str):
        """Event process handle function, overwritten in sub-class."""
        tg_fn = getattr(self, "on_key", None)
        if tg_fn is not None and callable(tg_fn):
            tg_fn(key)

        tg_name = self._event_map.get(key)
        if tg_name is None:
            return

        tg_fn = getattr(self, tg_name, None)
        if tg_fn is not None and callable(tg_fn):
            tg_fn()


class Container(Component):
    """Multiple components are stacked, only the activated sub-component can be rendered."""

    def __init__(
        self,
        children: Dict[str, "Component"],
        x: int = 0,
        y: int = 0,
        size: Optional[Tuple[int, int]] = None,
        start_name: Optional[str] = None,
        switch_handle: Optional[Callable[[str], str]] = None,
    ) -> None:
        super().__init__(x, y, size)

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

    def resize(self, size):
        self._size = size

        # let children process resize.
        for child in self.children.values():
            child.resize(size)

    def accept(self, action, **data):
        # sourcery skip: remove-unnecessary-else, swap-if-else-branches
        if action == "goto" and (name := data.get("target")) is not None:
            child = self.switch_child(name)
            child.update(action, **data)
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
            logger().debug(f"name: {name}")
            self.switch_child(name)

    def switch_child(self, name: str) -> "Component":
        """Choice which child should be activated."""
        child = None

        if name in self.children:
            # Has component be activated should deactivate.
            for component in self.children.values():
                if component.is_activated():
                    component.deactivate()
            # Activate the new choice component.
            self.children[name].activate()
            self.children[name]._render()
            child = self.children[name]

        return child


class RowPanel(Component):
    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[Tuple[int, int]] = None,
        content: Optional[List[str]] = None,
    ) -> None:
        super().__init__(x, y, size)

        self._content = content
        self._range = self._size[1]

        self._index = 0

        self._r = [0, self._size[1]]  # display range.

    def resize(self, size):
        self._size = size
        self._range = size[1]

        # TODO:
        self.fresh()

    def _render(self, size: Optional[Tuple[int, int]] = None):
        if self._content:
            Render.draw(
                self._content[self._index : self._index + self._range],
                self.x,
                self.y,
                self._size,
            )

    def scroll_up(self, line: int = 1):
        self._index = max(self._index - line, 0)
        self._render()

    def scroll_down(self, line: int = 1):
        self._index = min(self._index + line, len(self._content) - self._range)
        self._render()


class ItemSelector(Component):
    CURSOR: str = ""
    BINDINGS: Optional[List[Tuple]] = None

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        size: Optional[Tuple[int, int]] = None,
        content: Optional[List[str]] = None,
    ) -> None:
        super().__init__(x, y, size)

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

    def resize(self, size):
        self._size = size

        self.fresh()
        self.content_len = len(self.content) - 1

    def update(self, action, **data):
        pass

    def _render(self, size: Optional[Tuple[int, int]] = None):
        if not self.content:
            return

        dis = []
        for no, item in enumerate(
            self.content[self._r_start : self._r_start + self._size[1]],
            start=self._r_start,
        ):
            if no == self.curr_no:
                dis.append(f"{self.CURSOR}{item}")
            else:
                dis.append(f" {item}")

        Render.draw(dis, self.x, self.y, self._size)

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


class Alert(Component):
    pass
