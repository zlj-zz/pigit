# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_popup.py
Description: Popup offset clamp and dismiss_on_miss mouse contract.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx, set_overlay_host
from pigit.termui.component import Component
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.root import ComponentRoot
from pigit.termui.surface import Surface
from pigit.termui.types import LayerKind
from pigit.termui.widgets.popup import AlertDialog, Popup


class _FramedChild(Component):
    """Minimal Popup child that satisfies the ``_outer_w`` layout contract."""

    def __init__(self, outer_w: int = 20, outer_h: int = 6) -> None:
        super().__init__()
        self._outer_w = outer_w
        self.outer_row_count = outer_h


class _Body(Component):
    """Empty body for ComponentRoot."""


def test_popup_offset_clamps_to_terminal():
    child = _FramedChild(20, 6)
    popup = Popup(child, offset=(100, 100))
    popup.resize((40, 20))
    # th-oh=14, tw-ow=20 → clamped to those maxima; 1-based x/y = +1.
    assert child.x == 15
    assert child.y == 21
    assert child._size == (20, 6)


def test_popup_offset_none_still_centers():
    child = _FramedChild(20, 6)
    popup = Popup(child, offset=None)
    popup.resize((40, 20))
    assert child.x == 8
    assert child.y == 11


def _open_modal(root: ComponentRoot, popup: Popup) -> None:
    set_overlay_host(root)
    popup.resize(root._size)
    popup.show()
    popup.begin_session()


def test_dismiss_on_miss_closes_and_restores_focus():
    token = _runtime_ctx.set(RuntimeContext())
    try:
        body = _Body()
        body.resize((40, 20))
        root = ComponentRoot(body)
        root.resize((40, 20))
        root.mount()

        child = _FramedChild(10, 4)
        popup = Popup(child, offset=(2, 2), dismiss_on_miss=True)
        _open_modal(root, popup)
        assert popup.open is True
        assert root._layer_stack.top(LayerKind.MODAL) is popup

        miss = MouseEvent(col=39, row=19, button=MouseButton.LEFT, kind=MouseKind.PRESS)
        assert root._handle_mouse(miss) is True
        assert popup.open is False
        assert root._layer_stack.top(LayerKind.MODAL) is None
        assert root._focus_manager.get_focus_leaf() is body
    finally:
        _runtime_ctx.reset(token)


def test_dismiss_on_miss_false_keeps_modal_open():
    token = _runtime_ctx.set(RuntimeContext())
    try:
        body = _Body()
        body.resize((40, 20))
        root = ComponentRoot(body)
        root.resize((40, 20))
        root.mount()

        child = _FramedChild(10, 4)
        popup = Popup(child, offset=(2, 2), dismiss_on_miss=False)
        _open_modal(root, popup)

        miss = MouseEvent(col=39, row=19, button=MouseButton.LEFT, kind=MouseKind.PRESS)
        assert root._handle_mouse(miss) is True
        assert popup.open is True
        assert root._layer_stack.top(LayerKind.MODAL) is popup
    finally:
        _runtime_ctx.reset(token)


def test_dismiss_on_miss_release_does_not_close():
    """The release tailing the opening click must not dismiss the picker.

    Regression: clicking the Header tab slot opens the anchored popup on the
    press; the same click's release lands outside it and was closing it at
    once. Only an outside PRESS dismisses.
    """
    token = _runtime_ctx.set(RuntimeContext())
    try:
        body = _Body()
        body.resize((40, 20))
        root = ComponentRoot(body)
        root.resize((40, 20))
        root.mount()

        child = _FramedChild(10, 4)
        popup = Popup(child, offset=(2, 2), dismiss_on_miss=True)
        _open_modal(root, popup)
        assert popup.open is True

        release = MouseEvent(
            col=39, row=19, button=MouseButton.LEFT, kind=MouseKind.RELEASE
        )
        assert root._handle_mouse(release) is True
        assert popup.open is True  # release miss is swallowed, not dismissed

        press = MouseEvent(
            col=39, row=19, button=MouseButton.LEFT, kind=MouseKind.PRESS
        )
        assert root._handle_mouse(press) is True
        assert popup.open is False  # a real outside press closes
    finally:
        _runtime_ctx.reset(token)


# ── The overlay callback boundary ──


def test_alert_on_result_may_quit():
    """An answer may legitimately decide to quit — "N operations are still
    running, quit anyway?" is exactly that. This boundary swallows ordinary
    callback failures, but swallowing a quit request would leave the key
    doing nothing at all."""
    from pigit.termui.event_loop import ExitEventLoop
    from pigit.termui.widgets.popup import AlertDialog

    dialog = AlertDialog(on_result=lambda _ok: None)
    dialog.end_session = lambda: None
    dialog.hide = lambda: None
    dialog._pane.reset_state = lambda: None
    dialog._pane._on_result = Mock(side_effect=ExitEventLoop("Quit", force=True))

    with pytest.raises(ExitEventLoop):
        dialog._finish_alert(True)


def test_alert_on_result_failures_are_still_contained():
    from pigit.termui.widgets.popup import AlertDialog

    dialog = AlertDialog(on_result=lambda _ok: None)
    dialog.end_session = lambda: None
    dialog.hide = lambda: None
    dialog._pane.reset_state = lambda: None
    dialog._pane._on_result = Mock(side_effect=RuntimeError("boom"))

    dialog._finish_alert(True)  # must not raise


# ── AlertDialog height cap and scrolling ──
#
# A dialog taller than the terminal was drawn from row 0 and clipped at the
# bottom, which took the footer with it: a batch-undo confirm of a dozen
# records rendered 31 rows on an 80x24 terminal with neither OK nor Cancel
# on screen, leaving Esc as the only visible-free way out.


def _long_message(records: int = 12) -> str:
    """The shape `_confirm_reverse_range` builds for a multi-record undo."""
    lines = "\n".join(
        f"  - Discarded a{i}.py: git checkout -- a{i}.py" for i in range(records)
    )
    return f"Undo: Staged {records} file(s)\n{lines}\nRun:  git add a.py"


def _open_alert(message: str, size: tuple[int, int]):
    """Open a real AlertDialog on a terminal of *size*; return it and a paint."""
    token = _runtime_ctx.set(RuntimeContext())
    body = _Body()
    body.resize(size)
    root = ComponentRoot(body)
    root.resize(size)
    root.mount()
    set_overlay_host(root)
    dialog = AlertDialog(on_result=lambda _ok: None)
    dialog.resize(size)
    dialog.alert(message, lambda _ok: None)
    return token, dialog


def _painted(dialog, size: tuple[int, int]) -> list[str]:
    surface = Surface(*size)
    dialog.paint(surface)
    return ["".join(c.char for c in row).rstrip() for row in surface.rows()]


@pytest.mark.parametrize("size", [(80, 24), (80, 12), (80, 6)])
def test_a_long_message_never_pushes_the_buttons_off_screen(size):
    """The footer carries the only visible way to answer the dialog."""
    token, dialog = _open_alert(_long_message(), size)
    try:
        rows = _painted(dialog, size)
        text = " ".join(rows)
        assert "OK" in text
        assert "Cancel" in text
        assert dialog._pane.outer_row_count <= size[1]
    finally:
        _runtime_ctx.reset(token)


def test_a_short_message_is_left_alone():
    token, dialog = _open_alert("Merge feat into main?", (80, 24))
    try:
        rows = _painted(dialog, (80, 24))
        assert "Merge feat into main?" in "\n".join(rows)
        assert dialog._pane._frame.title == "Confirm"  # no scroll marker
        assert dialog._pane._scroll_i == 0
    finally:
        _runtime_ctx.reset(token)


def test_the_title_reports_which_lines_are_showing():
    token, dialog = _open_alert(_long_message(), (80, 12))
    try:
        _painted(dialog, (80, 12))
        pane = dialog._pane
        assert pane._frame.title == f"Confirm (1-{pane._max_body_rows()} of {pane._body_lines})"

        pane._scroll_down()
        _painted(dialog, (80, 12))
        assert pane._scroll_i == 1
        assert pane._frame.title.startswith("Confirm (2-")
    finally:
        _runtime_ctx.reset(token)


def test_scrolling_is_clamped_to_the_lines_that_exist():
    token, dialog = _open_alert(_long_message(), (80, 12))
    try:
        _painted(dialog, (80, 12))
        pane = dialog._pane
        limit = pane._body_lines - pane._max_body_rows()

        page = pane._max_body_rows()
        pane._scroll_page_down()
        assert pane._scroll_i == page
        # Paging past the end stops at the last full window, not beyond it.
        pane._scroll_page_down()
        pane._scroll_page_down()
        assert pane._scroll_i == limit
        pane._scroll_down()
        assert pane._scroll_i == limit
        pane._scroll_up()
        assert pane._scroll_i == limit - 1
        pane._scroll_page_up()
        pane._scroll_page_up()
        pane._scroll_page_up()
        assert pane._scroll_i == 0  # not before the start
    finally:
        _runtime_ctx.reset(token)


def test_a_shrink_re_clamps_the_window_and_keeps_the_footer():
    """A resize changes how many lines fit, so the window has to be re-clamped
    — otherwise it opens past the end of a now-shorter message window."""
    token, dialog = _open_alert(_long_message(), (80, 24))
    try:
        pane = dialog._pane
        _painted(dialog, (80, 24))
        pane._scroll_by(pane._body_lines)  # scroll to the very bottom
        bottom = pane._scroll_i
        assert bottom > 0

        dialog.resize((80, 10))
        rows = _painted(dialog, (80, 10))
        assert pane._scroll_i <= pane._body_lines - pane._max_body_rows()
        assert "OK" in " ".join(rows)
    finally:
        _runtime_ctx.reset(token)


def test_the_footer_is_still_clickable_when_the_message_is_capped():
    """Hit-testing reads the footer row's position, which the cap moves."""
    from pigit.termui.mouse import MouseButton, MouseKind

    size = (80, 12)
    token, dialog = _open_alert(_long_message(), size)
    try:
        _painted(dialog, size)
        pane = dialog._pane
        cr, cc, _cw, ch = pane._frame.content_rect(0, 0)
        footer_row0 = cr + min(ch, len(pane._content_rows)) - 1
        footer = pane._footer_plain()
        ok_col = cc + footer.index("OK")
        answers: list[bool] = []
        dialog._pane._on_result = answers.append

        event = MouseEvent(
            col=ok_col + 1, row=footer_row0 + 1,
            button=MouseButton.LEFT, kind=MouseKind.PRESS,
        )
        assert pane.handle_mouse(event) is True
    finally:
        _runtime_ctx.reset(token)
