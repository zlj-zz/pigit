# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_components_overlay.py
Description: Tests for Toast, Sheet, HelpPanel and overlay components.
Author: Zev
Date: 2026-04-18
"""

import pytest
from unittest.mock import MagicMock

from pigit.termui.component import Component
from pigit.termui import ToastPosition
from pigit.termui.widgets import (
    AlertDialogBody,
    HelpEntry,
    HelpPanel,
    Popup,
    Sheet,
    Toast,
)
from pigit.termui.types import OverlayDispatchResult
from pigit.termui.surface import Surface
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx


@pytest.fixture(autouse=True)
def _runtime_context():
    """Provide a fresh RuntimeContext for overlay tests."""
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    yield
    _runtime_ctx.reset(token)


class _Leaf(Component):
    NAME = "leaf"

    def paint(self, surface):
        pass

    def refresh(self):
        pass


class DummyBody(Component):
    NAME = "dummy"

    def paint(self, surface):
        pass

    def refresh(self):
        pass


def _make_root(body):
    """Create a ComponentRoot and wire it into the current RuntimeContext."""
    from pigit.termui.root import ComponentRoot

    root = ComponentRoot(body)
    runtime = RuntimeContext.current()
    if runtime is not None:
        runtime.overlay_host = root
        runtime.focus_manager = root._focus_manager
    return root


class TestOverlayContext:
    def test_show_toast_with_host(self):
        """验证 show_toast 在 overlay host context 下能工作"""
        from pigit.termui.overlay import show_toast
        from pigit.termui.root import ComponentRoot

        root = _make_root(DummyBody())
        root.resize((80, 24))

        result = show_toast("test message", duration=2.0)

        # 应该成功创建 Toast
        assert result is not None
        assert result.message == "test message"

    def test_show_toast_no_host_returns_none(self):
        """验证无 overlay host context 时返回 None"""
        from pigit.termui._runtime_context import (
            get_overlay_host,
            reset_overlay_host,
        )
        from pigit.termui.overlay import show_toast

        # 清除 overlay host
        reset_overlay_host()
        assert get_overlay_host() is None
        result = show_toast("test message")
        assert result is None

    def test_show_sheet_with_host(self):
        """验证 show_sheet 在 overlay host context 下能工作"""
        from pigit.termui.overlay import show_sheet
        from pigit.termui.root import ComponentRoot

        root = _make_root(DummyBody())
        root.resize((80, 24))

        inner = _Leaf()
        result = show_sheet(inner, height=5)

        assert result is not None

    def test_show_toast_position_parameter(self):
        """验证 show_toast 支持传递 position 参数"""
        from pigit.termui.overlay import show_toast
        from pigit.termui.root import ComponentRoot

        root = _make_root(DummyBody())
        root.resize((80, 24))

        result = show_toast("test", duration=2.0, position=ToastPosition.BOTTOM_LEFT)

        assert result is not None
        assert result._position == ToastPosition.BOTTOM_LEFT


class TestToast:
    def test_toastpaint(self):
        # 使用无动画的 Toast 以确保立即可见
        toast = Toast(
            "Hello World", duration=5.0, enter_duration=0.0, exit_duration=0.0
        )
        surface = Surface(40, 10)
        toast.resize((40, 10))  # 新实现需要 resize
        toast.paint(surface)

        # TOP_RIGHT 位置，内容在边框内（第2行，因为第1行是上边框）
        # 找到包含 "Hello World" 的行
        found = False
        for row in surface._rows:
            combined = "".join(c.char for c in row)
            if "Hello World" in combined:
                found = True
                break
        assert found, "Toast message not found in rendered surface"

    def test_toast_render_long_message_truncates(self):
        msg = "A" * 100
        # 使用无动画的 Toast 以确保立即可见
        toast = Toast(msg, duration=5.0, enter_duration=0.0, exit_duration=0.0)
        surface = Surface(20, 10)
        toast.resize((20, 10))  # 新实现需要 resize
        toast.paint(surface)

        # TOP_RIGHT 位置在第1行附近，外框占用空间
        row_text = surface._rows[2]  # 边框内行
        combined = "".join(c.char for c in row_text).rstrip()
        # 内容应该被截断以适应内框宽度
        assert len(combined) <= 20  # surface.width

    def test_toast_is_expired(self):
        clock = MagicMock(return_value=0.0)
        toast = Toast("msg", duration=2.0, clock=clock)
        assert not toast.is_expired()
        clock.return_value = 3.0
        assert toast.is_expired()

    def test_toast_dispatch_dropped(self):
        toast = Toast("msg")
        assert toast.dispatch_overlay_key("k") is OverlayDispatchResult.DROPPED_UNBOUND

    def test_toast_hide_sets_open_false(self):
        toast = Toast("msg")
        assert toast.open is True
        toast.hide()
        assert toast.open is False

    def test_toast_with_box_border(self):
        """验证 Toast 绘制了边框字符（┌─┐等）"""
        toast = Toast("Hello", duration=5.0)
        surface = Surface(40, 10)
        toast.resize((40, 10))
        toast.paint(surface)

        # 检查边框字符是否出现在 surface 上
        all_chars = []
        for row in surface._rows:
            all_chars.extend(c.char for c in row)
        all_text = "".join(all_chars)

        # BoxFrame 使用的边框字符
        assert "┌" in all_text or "─" in all_text or "│" in all_text

    @pytest.mark.parametrize(
        "position, top, left",
        [
            (ToastPosition.TOP_RIGHT, True, False),
            (ToastPosition.BOTTOM_LEFT, False, True),
            (ToastPosition.TOP_LEFT, True, True),
            (ToastPosition.BOTTOM_RIGHT, False, False),
        ],
    )
    def test_toast_position(self, position, top, left):
        """Verify each ToastPosition computes the correct base area."""
        toast = Toast("Test", duration=5.0, position=position)
        surface = Surface(100, 10)
        toast.resize((100, 10))
        toast._rebuild_frame()

        base_row, base_col = toast._compute_base_position(surface)
        if top:
            assert base_row == 1
        else:
            assert base_row > surface.height // 2
        if left:
            assert base_col == 1
        else:
            assert base_col > surface.width // 2

    def test_toast_position_center(self):
        toast = Toast("Hi", duration=5.0, position=ToastPosition.CENTER)
        toast._rebuild_frame()
        surface = Surface(80, 24)
        row, col = toast._compute_base_position(surface)
        assert abs(row - (24 - toast.outer_row_count) // 2) <= 1
        assert abs(col - (80 - toast._outer_w) // 2) <= 1
        assert toast._compute_slide_offset(0.0) == 0
        assert toast._compute_slide_offset(0.1) == 0

    def test_toast_spin_uses_info_chrome(self):
        from pigit.termui.feedback import FeedbackKind, style_for
        from pigit.termui.theme import get_theme

        toast = Toast(
            "Pulling",
            duration=3600.0,
            position=ToastPosition.CENTER,
            spin=True,
            enter_duration=0.0,
            exit_duration=0.0,
        )
        toast.resize((80, 24))
        toast._rebuild_frame()
        assert toast._frame is not None
        assert toast._frame.fg == style_for(FeedbackKind.INFO).fg
        glyph, text = toast._line_segments[0]
        assert glyph.fg == style_for(FeedbackKind.INFO).fg
        assert text.fg == get_theme().fg_primary
        assert "Pulling" in text.text

    def test_toast_spin_enforces_minimum_inner_width(self):
        toast = Toast(
            "x",
            duration=3600.0,
            position=ToastPosition.CENTER,
            spin=True,
            enter_duration=0.0,
            exit_duration=0.0,
        )
        toast.resize((80, 24))
        toast._rebuild_frame()
        assert toast._frame is not None
        assert toast._frame.inner_width >= 32

    def test_toast_spin_advances_frame_on_timer_tick(self):
        toast = Toast(
            "Pushing",
            duration=3600.0,
            position=ToastPosition.CENTER,
            spin=True,
            enter_duration=0.0,
            exit_duration=0.0,
        )
        toast.resize((80, 24))
        toast._rebuild_frame()
        first = "".join(s.text for s in toast._line_segments[0])
        toast._advance_spin_frame()
        toast._rebuild_frame()
        second = "".join(s.text for s in toast._line_segments[0])
        assert first != second
        assert "Pushing" in second

    def test_toast_slide_in_animation_left(self):
        """验证左侧位置的滑入动画偏移方向正确（水平方向）"""
        clock = MagicMock(return_value=0.0)
        toast = Toast(
            "Test",
            duration=5.0,
            position=ToastPosition.TOP_LEFT,
            enter_duration=0.5,
            clock=clock,
        )
        toast._outer_w = 15  # 设置外框宽度用于动画计算

        # 动画开始时（elapsed=0），应该有负偏移（在屏幕左侧外）
        offset = toast._compute_slide_offset(0.0)
        assert offset < 0

        # 动画进行中（elapsed=0.25），偏移应该变小（向右靠近）
        offset_mid = toast._compute_slide_offset(0.25)
        assert offset_mid < 0
        assert offset_mid > offset  # 向目标位置靠近

        # 动画结束时（elapsed >= enter_duration），偏移为0
        offset_end = toast._compute_slide_offset(0.5)
        assert offset_end == 0

    def test_toast_slide_in_animation_right(self):
        """验证右侧位置的滑入动画偏移方向正确（水平方向）"""
        toast = Toast(
            "Test",
            duration=5.0,
            position=ToastPosition.TOP_RIGHT,
            enter_duration=0.5,
        )
        toast._outer_w = 15  # 设置外框宽度用于动画计算

        # 动画开始时，应该有正偏移（在屏幕右侧外）
        offset = toast._compute_slide_offset(0.0)
        assert offset > 0

        # 动画结束时，偏移为0
        offset_end = toast._compute_slide_offset(0.5)
        assert offset_end == 0

    def test_toast_slide_out_extends_lifetime(self):
        """验证 is_expired() 包含 exit_duration"""
        clock = MagicMock(return_value=0.0)
        toast = Toast("msg", duration=2.0, exit_duration=0.5, clock=clock)

        # 2.0 秒时（duration 结束但未超过 exit_duration），未过期
        clock.return_value = 2.0
        assert not toast.is_expired()

        # 2.5+ 秒时（超过 duration + exit_duration），过期
        clock.return_value = 2.51
        assert toast.is_expired()

    def test_toast_skips_render_when_offscreen(self):
        """验证完全在屏幕外时不绘制"""
        toast = Toast("Test", duration=5.0, position=ToastPosition.TOP_RIGHT)
        surface = Surface(40, 10)
        toast.resize((40, 10))

        # 通过设置极端的偏移使 Toast 完全在屏幕外
        # 手动修改 outer_row_count 使 offset 计算导致完全超出
        toast.outer_row_count = 100  # 很大的高度

        # 不应抛出异常，且不应绘制任何内容
        toast.paint(surface)

    def test_toast_skips_render_when_terminal_too_small(self):
        """验证 surface.width < 4 or surface.height < 3 时直接返回"""
        toast = Toast("Test", duration=5.0)

        # 太窄的终端
        surface_narrow = Surface(3, 10)
        toast.paint(surface_narrow)  # 不应抛出异常

        # 太矮的终端
        surface_short = Surface(40, 2)
        toast.paint(surface_short)  # 不应抛出异常

    def test_toast_resizes_during_animation(self):
        """验证调用 resize() 后 _needs_rebuild 被正确置位"""
        toast = Toast("Test", duration=5.0)
        toast._needs_rebuild = False

        toast.resize((80, 24))

        assert toast._needs_rebuild is True
        assert toast._term_size == (80, 24)

    def test_toast_animation_clipped_when_duration_too_short(self):
        """验证 enter_duration + exit_duration > duration 时动画被禁用"""
        toast = Toast(
            "Test",
            duration=0.3,
            enter_duration=0.2,
            exit_duration=0.2,  # 总和 0.4 > 0.3
        )

        # 动画应该被禁用
        assert toast._enter_duration == 0.0
        assert toast._exit_duration == 0.0

        # offset 始终为 0
        offset = toast._compute_slide_offset(0.0)
        assert offset == 0
        offset_mid = toast._compute_slide_offset(0.15)
        assert offset_mid == 0

    def test_toast_multiline_message(self):
        """多行消息保留全部行（上限内）"""
        toast = Toast("Line1\nLine2\nLine3", duration=5.0)
        surface = Surface(40, 10)
        toast.resize((40, 10))
        toast._rebuild_frame()

        # 3 行内容在上限内，不截断
        assert len(toast._line_segments) == 3
        # outer_row_count 包含边框（上下各1行）
        assert toast.outer_row_count == 5  # 3 + 2

    def test_toast_overflow_truncates_with_marker(self):
        """超过行数上限时保留尾部（hint 可见）并在首行加省略标记"""
        lines = "\n".join(f"Line{i}" for i in range(9))  # 9 行 > 上限 6
        toast = Toast(lines, duration=5.0)
        surface = Surface(40, 10)
        toast.resize((40, 10))
        toast._rebuild_frame()

        assert len(toast._line_segments) == 6
        # Head is marked, tail is kept so actionable hint lines survive.
        assert any(seg.text == "… " for seg in toast._line_segments[0])
        assert "Line8" in "".join(s.text for s in toast._line_segments[-1])

    def test_toast_bottom_pad_lifts_bottom_position(self):
        """bottom_pad reserves rows above app chrome like the footer."""
        toast = Toast(
            "Hi",
            duration=5.0,
            position=ToastPosition.BOTTOM_RIGHT,
            bottom_pad=2,
        )
        surface = Surface(100, 20)
        toast.resize((100, 20))
        toast._rebuild_frame()
        base_row, _ = toast._compute_base_position(surface)
        # 20 rows, toast outer height 3: 20 - 3 - 1 - 2 = 14; footer rows 18-19.
        assert base_row == 14
        assert base_row + toast.outer_row_count <= surface.height - 2

    def test_toast_cjk_content_truncate_by_width(self):
        """验证 CJK 字符消息按显示宽度截断，不破坏边框对齐"""
        # CJK 字符宽度为 2，这里用 "中" 重复多次
        toast = Toast("中" * 50, duration=5.0)
        surface = Surface(20, 10)
        toast.resize((20, 10))
        toast._rebuild_frame()

        # 内容应该被截断以适应终端宽度
        max_line_len = max(
            sum(len(seg.text) for seg in line) for line in toast._line_segments
        )
        # 内框宽度最大为 surface.width - 4（左右边框+内边距）
        assert max_line_len <= 16  # 20 - 4

    def test_toast_exit_animation_slide(self):
        """验证退出动画的水平滑出偏移计算正确"""
        toast = Toast(
            "Test",
            duration=2.0,
            position=ToastPosition.TOP_RIGHT,
            enter_duration=0.0,
            exit_duration=0.5,
        )
        toast._outer_w = 15  # 设置外框宽度用于动画计算

        # 稳定期，无偏移
        offset_stable = toast._compute_slide_offset(1.0)
        assert offset_stable == 0

        # 退出动画开始（elapsed > duration - exit_duration = 1.5）
        # 使用较晚的时间点确保有明显偏移
        offset_exit_late = toast._compute_slide_offset(1.9)
        # progress = (2.0 - 1.9) / 0.5 = 0.2, offset = int(16 * 0.8) = 12
        assert offset_exit_late > 0  # 向右滑出

        # 退出动画结束（elapsed == duration）
        offset_exit_end = toast._compute_slide_offset(2.0)
        assert offset_exit_end == 16  # 完全滑出屏幕（宽度 + 1，确保彻底消失）


class TestSheet:
    def test_sheetpaint_draws_child_below_default_border(self):
        child = MagicMock()
        child.paint = MagicMock()
        sheet = Sheet(child, height=3)
        sheet._size = (20, 3)

        surface = Surface(20, 10)
        sheet.paint(surface)

        child.paint.assert_called_once()
        sub = child.paint.call_args[0][0]
        # Default: facing-edge rule; child gets sheet height minus 1
        assert sub.height == 2
        assert (sub._origin_row, sub._origin_col) == (8, 0)
        assert surface._rows[7][0].char == "─"
        assert surface._rows[7][19].char == "─"

    def test_sheetpaint_borderless(self):
        child = MagicMock()
        child.paint = MagicMock()
        sheet = Sheet(child, height=3, show_edge_rule=False)
        sheet._size = (20, 3)

        surface = Surface(20, 10)
        sheet.paint(surface)

        child.paint.assert_called_once()
        sub = child.paint.call_args[0][0]
        assert sub.height == 3
        assert (sub._origin_row, sub._origin_col) == (7, 0)

    def test_sheetpaint_with_border(self):
        child = MagicMock()
        child.paint = MagicMock()
        sheet = Sheet(child, height=3, show_edge_rule=True)
        sheet._size = (20, 3)

        surface = Surface(20, 10)
        sheet.paint(surface)

        child.paint.assert_called_once()
        sub = child.paint.call_args[0][0]
        # With border: child height is sheet height minus 1
        assert sub.height == 2
        assert (sub._origin_row, sub._origin_col) == (8, 0)
        assert surface._rows[7][0].char == "─"
        assert surface._rows[7][19].char == "─"

    def test_sheetpaint_edge_fg_colors_rule_and_title(self):
        child = MagicMock()
        child.paint = MagicMock()
        accent = (150, 200, 255)
        sheet = Sheet(child, height=3, edge_fg=accent, title_core=" · Hi · ")
        sheet._size = (20, 3)
        surface = Surface(20, 10)
        sheet.paint(surface)
        row = surface._rows[7]
        text = "".join(c.char for c in row)
        assert "Hi" in text
        # Rule fill and title core both take the accent when edge_fg is set.
        assert row[0].fg == accent
        assert row[text.index("Hi")].fg == accent

    def test_sheetpaint_default_rule_uses_theme_dim(self):
        child = MagicMock()
        child.paint = MagicMock()
        sheet = Sheet(child, height=3)
        sheet._size = (20, 3)
        surface = Surface(20, 10)
        sheet.paint(surface)
        from pigit.termui.theme import get_theme

        assert surface._rows[7][0].fg == get_theme().fg_dim

    def test_sheet_top_edge_border_is_on_last_row(self):
        child = MagicMock()
        child.paint = MagicMock()
        sheet = Sheet(child, height=3, show_edge_rule=True, edge="top")
        sheet._size = (20, 3)
        surface = Surface(20, 10)
        sheet.paint(surface)
        sub = child.paint.call_args[0][0]
        assert sub.height == 2
        assert (sub._origin_row, sub._origin_col) == (0, 0)
        assert surface._rows[2][0].char == "─"
        assert surface._rows[2][19].char == "─"
        assert surface._rows[0][0].char != "─"

    def test_sheetpaint_zero_height_skips(self):
        child = MagicMock()
        sheet = Sheet(child, height=0)
        sheet._size = (20, 0)

        surface = Surface(20, 10)
        sheet.paint(surface)

        child.paint.assert_not_called()

    def test_sheet_dispatch_delegates_to_child(self):
        child = MagicMock()
        child.dispatch_overlay_key.return_value = OverlayDispatchResult.HANDLED_EXPLICIT
        sheet = Sheet(child, height=3)

        result = sheet.dispatch_overlay_key("k")
        assert result is OverlayDispatchResult.HANDLED_EXPLICIT
        child.dispatch_overlay_key.assert_called_once_with("k")

    def test_sheet_dispatch_routes_to_child_handle_event(self):
        child = _Leaf()
        sheet = Sheet(child, height=3)

        result = sheet.dispatch_overlay_key("k")
        assert result is OverlayDispatchResult.HANDLED_EXPLICIT

    def test_sheet_resize_sets_size_and_child_size(self):
        child = MagicMock()
        sheet = Sheet(child, height=6)
        sheet.resize((40, 20))

        assert sheet._size == (40, 6)
        # Default border: child height is sheet height minus 1
        child.resize.assert_called_once_with((40, 5))

    def test_sheet_resize_clamps_to_half_height(self):
        child = MagicMock()
        sheet = Sheet(child, height=100)
        sheet.resize((40, 20))

        assert sheet._size == (40, 10)
        # Default border: child height is sheet height minus 1
        child.resize.assert_called_once_with((40, 9))

    def test_sheet_resize_with_border_reduces_child_height(self):
        child = MagicMock()
        sheet = Sheet(child, height=6, show_edge_rule=True)
        sheet.resize((40, 20))

        assert sheet._size == (40, 6)
        # With border: child height is sheet height minus 1
        child.resize.assert_called_once_with((40, 5))

    def test_sheet_hit_test_top_edge_border_not_swallowed(self):
        """The border is the last sheet row; the row above it must reach the child."""
        child = MagicMock()
        child._size = (20, 5)
        child._hit_test.return_value = (child, 5, 5)
        sheet = Sheet(child, height=6, show_edge_rule=True, edge="top")
        sheet.resize((20, 20))
        # Row 5 (1-based) is the last content row; it must hit the child.
        hit = sheet._hit_test(3, 5)
        assert hit[0] is child
        child._hit_test.assert_called_once_with(3, 5)
        child._hit_test.reset_mock()
        # Row 6 (1-based) is the border; it belongs to the sheet itself.
        hit = sheet._hit_test(3, 6)
        assert hit[0] is sheet
        child._hit_test.assert_not_called()

    def test_sheet_hit_test_bottom_edge_border_first_row(self):
        """For a bottom sheet the border is the first row; content rows offset by one."""
        child = MagicMock()
        child._size = (20, 5)
        child._hit_test.return_value = (child, 5, 1)
        sheet = Sheet(child, height=6, show_edge_rule=True)
        sheet.resize((20, 20))
        # Row 15 (1-based) is the border.
        hit = sheet._hit_test(3, 15)
        assert hit[0] is sheet
        # Row 16 (1-based) is the first content row, mapped to child row 1.
        hit = sheet._hit_test(3, 16)
        assert hit[0] is child
        child._hit_test.assert_called_once_with(3, 1)

    def test_sheet_hide_sets_open_false(self):
        child = _Leaf()
        sheet = Sheet(child, height=3)
        assert sheet.open is True
        sheet.hide()
        assert sheet.open is False

    def test_sheet_top_edge_renders_at_row_zero(self):
        child = MagicMock()
        child.paint = MagicMock()
        sheet = Sheet(child, height=3, edge="top")
        sheet._size = (20, 3)
        surface = Surface(20, 10)
        sheet.paint(surface)
        sub = child.paint.call_args[0][0]
        assert (sub._origin_row, sub._origin_col) == (0, 0)

    def test_sheet_bottom_pad_shifts_origin(self):
        """bottom_pad lifts the sheet above footer chrome rows."""
        child = MagicMock()
        child.paint = MagicMock()
        sheet = Sheet(child, height=3, bottom_pad=2)
        sheet._size = (20, 3)
        surface = Surface(20, 10)
        sheet.paint(surface)
        sub = child.paint.call_args[0][0]
        # No-pad child origin is 8; pad=2 → sheet top 5, child origin 6.
        assert sheet._origin_row(10, 3) == 5
        assert (sub._origin_row, sub._origin_col) == (6, 0)

    def test_sheet_top_pad_shifts_origin(self):
        """top_pad drops a top sheet below header chrome rows."""
        child = MagicMock()
        child.paint = MagicMock()
        sheet = Sheet(child, height=3, edge="top", top_pad=2)
        sheet._size = (20, 3)
        surface = Surface(20, 10)
        sheet.paint(surface)
        sub = child.paint.call_args[0][0]
        assert sheet._origin_row(10, 3) == 2
        assert (sub._origin_row, sub._origin_col) == (2, 0)

    def test_sheet_resize_cap_respects_bottom_pad(self):
        """Height cap uses (term_h - chrome) so pads shrink the max sheet."""
        child = MagicMock()
        sheet = Sheet(child, height=100, bottom_pad=2, height_cap_fraction=0.5)
        sheet.resize((40, 10))
        assert sheet._size == (40, 4)

    def test_sheet_top_edge_resize_origin(self):
        child = MagicMock()
        sheet = Sheet(child, height=6, edge="top")
        sheet.resize((40, 20))
        assert sheet._size == (40, 6)
        assert sheet.x == 1
        assert sheet.y == 1

    def test_sheet_bg_none_still_clears_region(self):
        child = MagicMock()
        child.paint = MagicMock()
        sheet = Sheet(child, height=3, edge="top", bg=None)
        sheet._size = (20, 3)
        surface = Surface(20, 10)
        surface.draw_text_rgb(0, 0, "HELLO", bg=(1, 2, 3))
        sheet.paint(surface)
        assert surface._rows[0][0].char == " "
        assert surface._rows[0][0].bg is None
        assert surface._rows[0][4].char == " "

    def test_sheet_title_right_aligned_by_default(self):
        child = MagicMock()
        child.paint = MagicMock()
        sheet = Sheet(child, height=3, title_core=" · Commands · ")
        sheet._size = (24, 3)
        surface = Surface(24, 10)
        sheet.paint(surface)
        rule = "".join(c.char for c in surface._rows[7])
        assert rule.endswith(" · Commands · ─")
        assert rule.startswith("─")

    def test_compose_edge_rule_alignments(self):
        from pigit.termui.widgets.sheet import compose_edge_rule

        left, core, right = compose_edge_rule(20, " · Hi · ", align="left")
        assert left == "─"
        assert core == " · Hi · "
        assert right.startswith("─")

        left, core, right = compose_edge_rule(20, " · Hi · ", align="right")
        assert right == "─"
        assert core == " · Hi · "
        assert left.startswith("─")

        left, core, right = compose_edge_rule(21, " · Hi · ", align="center")
        assert core == " · Hi · "
        assert abs(len(left) - len(right)) <= 1

    def test_compose_edge_rule_truncates_long_core(self):
        from pigit.termui.widgets.sheet import compose_edge_rule

        left, core, right = compose_edge_rule(12, " · VeryLongTitle · ")
        assert left == "─" and right == "─"
        assert core.startswith(" · ")
        assert "…" in core


class TestHelpPanel:
    def test_help_panel_render_bindings(self):
        panel = HelpPanel()
        panel.set_entries([("j", "down"), ("k", "up")])
        surface = Surface(60, 20)
        panel.resize((60, 20))
        panel.paint(surface)

        # Frame should have drawn a border; content rows should include bindings.
        row_text = surface._rows[1]
        combined = "".join(c.char for c in row_text)
        assert "j" in combined or "down" in combined

    def test_help_panel_scroll_down_clamps(self):
        panel = HelpPanel()
        panel.set_entries([("a", "A")])
        panel.scroll_down()
        assert panel._offset == 0

    def test_help_panel_scroll_up_clamps_at_zero(self):
        panel = HelpPanel()
        # Need more entries than _scroll_h so scroll_down advances
        panel.set_entries(
            [
                ("a", "A"),
                ("b", "B"),
                ("c", "C"),
                ("d", "D"),
                ("e", "E"),
                ("f", "F"),
                ("g", "G"),
            ]
        )
        start = panel._offset
        # scroll down advances (inner_h defaults to >=5, so _scroll_h >=4)
        panel.scroll_down()
        panel.scroll_down()
        panel.scroll_down()
        assert panel._offset > start
        # scroll up retreats to zero
        while panel._offset > 0:
            panel.scroll_up()
        assert panel._offset == 0
        panel.scroll_up()
        assert panel._offset == 0

    def test_help_panel_min_inner_width_floor(self):
        """Short content still gets at least MIN_INNER_W on a wide terminal."""
        panel = HelpPanel()
        panel.set_entries([("?", "help"), ("q", "quit")])
        panel.resize((200, 40))
        assert panel._inner_w >= HelpPanel.MIN_INNER_W
        assert HelpPanel.MIN_INNER_W == 88

    def test_help_panel_keys_right_aligned_flat(self):
        """Shorter keys are left-padded so the key column is right-aligned."""
        panel = HelpPanel(inner_width=40)
        panel.set_entries([("?", "Toggle help"), ("ctrl+r", "Refresh")])
        panel.resize((80, 24))
        first = panel._lines[0]
        assert first.startswith(" ")
        assert "?" in first
        q_idx = first.index("?")
        ctrl_line = next(
            line for line in panel._lines if line.lstrip().startswith("ctrl+r")
        )
        ctrl_idx = ctrl_line.index("ctrl+r")
        assert q_idx + 1 == ctrl_idx + len("ctrl+r")

    def test_help_panel_keys_right_aligned_grouped(self):
        """Grouped rows keep group_indent then right-aligned keys."""
        panel = HelpPanel(inner_width=40)
        panel.set_grouped_entries(
            [
                ("Global", [("?", "Toggle help"), ("ctrl+r", "Refresh")]),
            ]
        )
        panel.resize((80, 24))
        data_lines = [
            ln for ln in panel._lines if ln.strip() and not ln.lstrip().startswith("[")
        ]
        short = next(ln for ln in data_lines if "?" in ln)
        long = next(ln for ln in data_lines if "ctrl+r" in ln)
        assert short.index("?") + 1 == long.index("ctrl+r") + len("ctrl+r")

    def test_help_panel_group_title_brackets(self):
        """Grouped section headers render as [Title]."""
        panel = HelpPanel(inner_width=40)
        panel.set_grouped_entries([("Global", [("?", "Toggle help")])])
        panel.resize((80, 24))
        assert panel._lines[0] == "[Global]"
        assert panel._line_segments[0][0].text == "[Global]"

    def test_help_panel_mouse_wheel_scrolls(self):
        """Wheel events scroll the help list like keyboard j/k."""
        from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind

        panel = HelpPanel(inner_width=40, inner_height=6)
        panel.set_entries([(str(i), f"desc {i}") for i in range(20)])
        panel.resize((80, 24))
        assert panel._offset == 0

        down = MouseEvent(
            button=MouseButton.WHEEL_DOWN, col=1, row=1, kind=MouseKind.PRESS
        )
        assert panel.handle_mouse(down) is True
        assert panel._offset == 1

        up = MouseEvent(button=MouseButton.WHEEL_UP, col=1, row=1, kind=MouseKind.PRESS)
        assert panel.handle_mouse(up) is True
        assert panel._offset == 0

        left = MouseEvent(button=MouseButton.LEFT, col=1, row=1, kind=MouseKind.PRESS)
        assert panel.handle_mouse(left) is False


class TestPopup:
    def _with_host(self, host):
        from pigit.termui._runtime_context import set_overlay_host

        set_overlay_host(host)

    def test_popup_toggle_opens_when_no_modal(self):
        from pigit.termui._runtime_context import reset_overlay_host

        host = MagicMock()
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = None
        child = _Leaf()
        popup = Popup(child)
        self._with_host(host)
        try:
            popup.toggle()
            assert popup.open is True
            host._layer_stack.push.assert_called_once()
        finally:
            reset_overlay_host()

    def test_popup_toggle_close_when_self_is_active(self):
        from pigit.termui._runtime_context import reset_overlay_host

        host = MagicMock()
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = None
        child = _Leaf()
        popup = Popup(child)
        self._with_host(host)
        try:
            popup.toggle()
            host._layer_stack.top.return_value = popup
            popup.toggle()
            assert popup.open is False
            host._layer_stack.pop.assert_called_once()
        finally:
            reset_overlay_host()

    def test_popup_toggle_blocked_when_other_modal_active(self):
        from pigit.termui._runtime_context import reset_overlay_host

        host = MagicMock()
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = MagicMock()
        child = _Leaf()
        popup = Popup(child)
        self._with_host(host)
        try:
            popup.toggle()
            assert popup.open is False
        finally:
            reset_overlay_host()

    def test_popup_dispatch_overlay_key_explicit(self):
        class _KeyChild(Component):
            NAME = "key_child"
            BINDINGS = [("x", "on_x")]

            def on_x(self):
                pass

            def paint(self, surface):
                pass

            def refresh(self):
                pass

        child = _KeyChild()
        popup = Popup(child)
        result = popup.dispatch_overlay_key("x")
        assert result is OverlayDispatchResult.HANDLED_EXPLICIT

    def test_help_panel_toggle_binding(self):
        """HelpPanel binds '?' to toggle and delegates to on_toggle callback."""
        toggled = []
        panel = HelpPanel(on_toggle=lambda: toggled.append(True))
        panel.toggle()
        assert toggled == [True]

    def test_help_panel_toggle_noop_without_callback(self):
        """HelpPanel.toggle() is safe when on_toggle is None."""
        panel = HelpPanel()
        panel.toggle()  # should not raise

    def test_popup_auto_binds_child_toggle(self):
        """Popup auto-wires its toggle() to child.set_on_toggle if available."""
        from pigit.termui._runtime_context import reset_overlay_host

        host = MagicMock()
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = None
        panel = HelpPanel()
        popup = Popup(panel)
        self._with_host(host)
        try:
            # Popup should have auto-bound its toggle to the panel
            panel.toggle()
            assert popup.open is True
            host._layer_stack.top.return_value = popup
            panel.toggle()
            assert popup.open is False
        finally:
            reset_overlay_host()

    def test_popup_fallback_swallows_unbound(self):
        child = _Leaf()
        popup = Popup(child)
        result = popup.dispatch_overlay_key("z")
        assert result is OverlayDispatchResult.DROPPED_UNBOUND

    def test_popuppaint_not_open_skips(self):
        child = _Leaf()
        popup = Popup(child)
        popup.open = False
        surface = Surface(40, 20)
        popup.paint(surface)
        # No exception and child not rendered

    def test_popuppaint_resizes_if_needed(self):
        child = _Leaf()
        popup = Popup(child)
        popup.open = True
        popup._term_size = (0, 0)
        surface = Surface(40, 20)
        popup.paint(surface)
        assert popup._term_size == (40, 20)


class TestAlertDialogBody:
    def test_alert_body_builds_content_lines(self):
        body = AlertDialogBody(
            shell=MagicMock(),
            message="Test message",
            on_result=lambda x: None,
        )
        body.resize((60, 20))  # large width so footer stays on one line
        body._rebuild_frame()
        plain = [" ".join(seg.text for seg in row) for row in body._content_rows]

        assert any("Test message" in line for line in plain)
        assert any("OK" in line for line in plain)
        assert any("Cancel" in line for line in plain)

    def test_alert_body_confirm_calls_shell_finish(self):
        shell = MagicMock()
        body = AlertDialogBody(
            shell=shell,
            message="m",
            on_result=lambda x: None,
        )
        body._confirm()
        shell._finish_alert.assert_called_once_with(True)

    def test_prepare_error_kind_uses_error_border(self):
        from pigit.termui.feedback import FeedbackKind, style_for

        body = AlertDialogBody(
            shell=MagicMock(),
            message="m",
            on_result=lambda x: None,
        )
        body.prepare("Discard?", lambda x: None, kind=FeedbackKind.ERROR)
        assert body._frame.fg == style_for(FeedbackKind.ERROR).fg

    def test_prepare_neutral_kind_uses_theme_primary(self):
        from pigit.termui.feedback import FeedbackKind
        from pigit.termui.theme import get_theme

        body = AlertDialogBody(
            shell=MagicMock(),
            message="m",
            on_result=lambda x: None,
        )
        body.prepare("Discard?", lambda x: None, kind=FeedbackKind.ERROR)
        body.prepare("Merge?", lambda x: None, kind=None)
        assert body._frame.fg == get_theme().fg_primary

    def test_footer_ok_uses_danger_color_for_error_kind(self):
        from pigit.termui.feedback import FeedbackKind
        from pigit.termui.theme import get_theme

        body = AlertDialogBody(
            shell=MagicMock(),
            message="m",
            on_result=lambda x: None,
        )
        body.prepare("Drop?", lambda x: None, kind=FeedbackKind.ERROR)
        body.resize((60, 20))
        body._rebuild_frame()
        footer = body._content_rows[-1]
        ok = next(seg for seg in footer if seg.text == "OK")
        assert ok.fg == get_theme().fg_danger

    def test_alert_body_default_width_is_three_sevenths_of_terminal(self):
        body = AlertDialogBody(
            shell=MagicMock(),
            message="m",
            on_result=lambda x: None,
        )
        body.resize((100, 20))  # term_cols = 100 → 3/7 = 42, above the floor
        body._rebuild_frame()
        assert body._inner_w == 100 * 3 // 7
        body.resize((60, 20))  # 3/7 = 25, but the 40-cell floor wins
        body._rebuild_frame()
        assert body._inner_w == 40

    def test_alert_body_wraps_fullwidth_chars_by_display_width(self):
        from pigit.termui.wcwidth_table import wcswidth

        # Char count fits the row, but full-width CJK pushes display width
        # over; wrapping must be display-width aware or the text paints the
        # frame border (regression for the reflog confirm dialog).
        body = AlertDialogBody(
            shell=MagicMock(),
            message="Recover to abc1234（commit: 修复问题 · 2h ago）",
            on_result=lambda x: None,
        )
        body.resize((60, 20))
        body._rebuild_frame()
        _cr, _cc, cw, _ch = body._frame.content_rect(0, 0)
        for row in body._content_rows:
            used = sum(max(0, wcswidth(seg.text)) for seg in row)
            assert used <= cw
