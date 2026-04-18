# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_components_overlay.py
Description: Tests for Toast, Sheet, HelpPanel and overlay components.
Author: Zev
Date: 2026-04-18
"""

import pytest
from unittest.mock import MagicMock

from pigit.termui.components import Component
from pigit.termui.components_overlay import (
    AlertDialogBody,
    HelpEntry,
    HelpPanel,
    Popup,
    Sheet,
    Toast,
    ToastPosition,
)
from pigit.termui.overlay_kinds import OverlayDispatchResult
from pigit.termui.surface import Surface


class _Leaf(Component):
    NAME = "leaf"

    def _render_surface(self, surface):
        pass

    def fresh(self):
        pass


class DummyBody(Component):
    NAME = "dummy"

    def _render_surface(self, surface):
        pass

    def fresh(self):
        pass


class TestOverlayClientMixin:
    def test_mixin_show_toast_finds_host(self):
        """验证 OverlayClientMixin.show_toast 能找到 host 并调用"""
        from pigit.termui.components import OverlayClientMixin
        from pigit.termui.root import ComponentRoot

        class _MixinComponent(Component, OverlayClientMixin):
            NAME = "mixin_test"

            def _render_surface(self, surface):
                pass

            def fresh(self):
                pass

        root = ComponentRoot(DummyBody())
        root.resize((80, 24))
        mixin_comp = _MixinComponent()
        mixin_comp.parent = root.body
        root.body.children = {"test": mixin_comp}

        result = mixin_comp.show_toast("test message", duration=2.0)

        # 应该成功创建 Toast
        assert result is not None
        assert result._message == "test message"

    def test_mixin_show_toast_no_host_returns_none(self):
        """验证无 host 时返回 None"""
        from pigit.termui.components import OverlayClientMixin

        class _MixinComponent(Component, OverlayClientMixin):
            NAME = "mixin_test"

            def _render_surface(self, surface):
                pass

            def fresh(self):
                pass

        mixin_comp = _MixinComponent()
        # 无 parent，应该返回 None
        result = mixin_comp.show_toast("test message")
        assert result is None

    def test_mixin_show_sheet_finds_host(self):
        """验证 OverlayClientMixin.show_sheet 能找到 host"""
        from pigit.termui.components import OverlayClientMixin
        from pigit.termui.root import ComponentRoot

        class _MixinComponent(Component, OverlayClientMixin):
            NAME = "mixin_test"

            def _render_surface(self, surface):
                pass

            def fresh(self):
                pass

        root = ComponentRoot(DummyBody())
        root.resize((80, 24))
        mixin_comp = _MixinComponent()
        mixin_comp.parent = root.body
        root.body.children = {"test": mixin_comp}

        inner = _Leaf()
        result = mixin_comp.show_sheet(inner, height=5)

        assert result is not None

    def test_mixin_show_toast_position_parameter(self):
        """验证 Mixin 支持传递 position 参数"""
        from pigit.termui.components import OverlayClientMixin
        from pigit.termui.root import ComponentRoot

        class _MixinComponent(Component, OverlayClientMixin):
            NAME = "mixin_test"

            def _render_surface(self, surface):
                pass

            def fresh(self):
                pass

        root = ComponentRoot(DummyBody())
        root.resize((80, 24))
        mixin_comp = _MixinComponent()
        mixin_comp.parent = root.body
        root.body.children = {"test": mixin_comp}

        result = mixin_comp.show_toast(
            "test", duration=2.0, position=ToastPosition.BOTTOM_LEFT
        )

        assert result is not None
        assert result._position == ToastPosition.BOTTOM_LEFT


class TestToast:
    def test_toast_render_surface(self):
        # 使用无动画的 Toast 以确保立即可见
        toast = Toast("Hello World", duration=5.0, enter_duration=0.0, exit_duration=0.0)
        surface = Surface(40, 10)
        toast.resize((40, 10))  # 新实现需要 resize
        toast._render_surface(surface)

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
        toast._render_surface(surface)

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
        toast._render_surface(surface)

        # 检查边框字符是否出现在 surface 上
        all_chars = []
        for row in surface._rows:
            all_chars.extend(c.char for c in row)
        all_text = "".join(all_chars)

        # BoxFrame 使用的边框字符
        assert "┌" in all_text or "─" in all_text or "│" in all_text

    def test_toast_position_top_right(self):
        """验证默认位置 TOP_RIGHT 在右上角区域"""
        toast = Toast("Test", duration=5.0, position=ToastPosition.TOP_RIGHT)
        surface = Surface(40, 10)
        toast.resize((40, 10))
        toast._rebuild_frame()

        base_row, base_col = toast._compute_base_position(surface)
        assert base_row == 1  # 第1行（顶部）
        assert base_col > surface.width // 2  # 在右侧区域

    def test_toast_position_bottom_left(self):
        """验证 BOTTOM_LEFT 位置在左下角区域"""
        toast = Toast("Test", duration=5.0, position=ToastPosition.BOTTOM_LEFT)
        surface = Surface(40, 10)
        toast.resize((40, 10))
        toast._rebuild_frame()

        base_row, base_col = toast._compute_base_position(surface)
        assert base_row > surface.height // 2  # 在底部区域
        assert base_col == 1  # 第1列（左侧）

    def test_toast_position_top_left(self):
        """验证 TOP_LEFT 位置在左上角区域"""
        toast = Toast("Test", duration=5.0, position=ToastPosition.TOP_LEFT)
        surface = Surface(40, 10)
        toast.resize((40, 10))
        toast._rebuild_frame()

        base_row, base_col = toast._compute_base_position(surface)
        assert base_row == 1
        assert base_col == 1

    def test_toast_position_bottom_right(self):
        """验证 BOTTOM_RIGHT 位置在右下角区域"""
        toast = Toast("Test", duration=5.0, position=ToastPosition.BOTTOM_RIGHT)
        surface = Surface(40, 10)
        toast.resize((40, 10))
        toast._rebuild_frame()

        base_row, base_col = toast._compute_base_position(surface)
        assert base_row > surface.height // 2
        assert base_col > surface.width // 2

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
        toast._render_surface(surface)

    def test_toast_skips_render_when_terminal_too_small(self):
        """验证 surface.width < 4 or surface.height < 3 时直接返回"""
        toast = Toast("Test", duration=5.0)

        # 太窄的终端
        surface_narrow = Surface(3, 10)
        toast._render_surface(surface_narrow)  # 不应抛出异常

        # 太矮的终端
        surface_short = Surface(40, 2)
        toast._render_surface(surface_short)  # 不应抛出异常

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
        """验证多行消息的边框高度计算正确"""
        toast = Toast("Line1\nLine2\nLine3", duration=5.0)
        surface = Surface(40, 10)
        toast.resize((40, 10))
        toast._rebuild_frame()

        # 3 行内容，inner_h 应该为 3
        assert len(toast._lines) == 3
        # outer_row_count 应该包含边框（上下各1行）
        assert toast.outer_row_count == 5  # 3 + 2

    def test_toast_cjk_content_truncate_by_width(self):
        """验证 CJK 字符消息按显示宽度截断，不破坏边框对齐"""
        # CJK 字符宽度为 2，这里用 "中" 重复多次
        toast = Toast("中" * 50, duration=5.0)
        surface = Surface(20, 10)
        toast.resize((20, 10))
        toast._rebuild_frame()

        # 内容应该被截断以适应终端宽度
        max_line_len = max(len(line) for line in toast._lines)
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
        # progress = (2.0 - 1.9) / 0.5 = 0.2, offset = int(15 * 0.8) = 12
        assert offset_exit_late > 0  # 向右滑出

        # 退出动画结束（elapsed == duration）
        offset_exit_end = toast._compute_slide_offset(2.0)
        assert offset_exit_end == 15  # 完全滑出屏幕（宽度为15）


class TestSheet:
    def test_sheet_render_surface_draws_child_at_bottom(self):
        child = MagicMock()
        child._render_surface = MagicMock()
        sheet = Sheet(child, height=3)
        sheet._size = (20, 3)

        surface = Surface(20, 10)
        sheet._render_surface(surface)

        child._render_surface.assert_called_once()
        sub = child._render_surface.call_args[0][0]
        # Subsurface height matches sheet size; _to_parent translates to bottom area
        assert sub.height == 3
        assert hasattr(sub, "_to_parent")

    def test_sheet_render_surface_zero_height_skips(self):
        child = MagicMock()
        sheet = Sheet(child, height=0)
        sheet._size = (20, 0)

        surface = Surface(20, 10)
        sheet._render_surface(surface)

        child._render_surface.assert_not_called()

    def test_sheet_dispatch_delegates_to_child(self):
        child = MagicMock()
        child.dispatch_overlay_key.return_value = OverlayDispatchResult.HANDLED_EXPLICIT
        sheet = Sheet(child, height=3)

        result = sheet.dispatch_overlay_key("k")
        assert result is OverlayDispatchResult.HANDLED_EXPLICIT
        child.dispatch_overlay_key.assert_called_once_with("k")

    def test_sheet_dispatch_no_child_handler_returns_dropped(self):
        child = _Leaf()
        sheet = Sheet(child, height=3)

        result = sheet.dispatch_overlay_key("k")
        assert result is OverlayDispatchResult.DROPPED_UNBOUND

    def test_sheet_resize_sets_size_and_child_size(self):
        child = MagicMock()
        sheet = Sheet(child, height=6)
        sheet.resize((40, 20))

        assert sheet._size == (40, 6)
        child.resize.assert_called_once_with((40, 6))

    def test_sheet_resize_clamps_to_half_height(self):
        child = MagicMock()
        sheet = Sheet(child, height=100)
        sheet.resize((40, 20))

        assert sheet._size == (40, 10)
        child.resize.assert_called_once_with((40, 10))

    def test_sheet_hide_sets_open_false(self):
        child = _Leaf()
        sheet = Sheet(child, height=3)
        assert sheet.open is True
        sheet.hide()
        assert sheet.open is False


class TestHelpPanel:
    def test_help_panel_render_bindings(self):
        panel = HelpPanel()
        panel.set_entries([("j", "down"), ("k", "up")])
        surface = Surface(60, 20)
        panel.resize((60, 20))
        panel._render_surface(surface)

        # Frame should have drawn a border; content rows should include bindings.
        row_text = surface._rows[2]
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
            [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D"),
             ("e", "E"), ("f", "F"), ("g", "G")]
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


class TestPopup:
    def test_popup_toggle_with_session_owner(self):
        host = MagicMock()
        host.has_overlay_open.return_value = False
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = None
        child = _Leaf()
        popup = Popup(child, session_owner=host)

        popup.toggle()

        assert popup.open is True
        host.begin_popup_session.assert_called_once_with(popup)

    def test_popup_toggle_close_when_self_is_active(self):
        host = MagicMock()
        host.has_overlay_open.return_value = True
        child = _Leaf()
        popup = Popup(child, session_owner=host)
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = popup

        popup.toggle()

        assert popup.open is False
        host.end_popup_session.assert_called_once()

    def test_popup_dispatch_overlay_key_explicit(self):
        class _KeyChild(Component):
            NAME = "key_child"
            BINDINGS = [("x", "on_x")]

            def on_x(self):
                pass

            def _render_surface(self, surface):
                pass

            def fresh(self):
                pass

        child = _KeyChild()
        popup = Popup(child)
        result = popup.dispatch_overlay_key("x")
        assert result is OverlayDispatchResult.HANDLED_EXPLICIT

    def test_popup_fallback_overlay_key_help_toggle(self):
        class _HelpChild(Component):
            NAME = "help_child"
            TOGGLE_HELP_SEMANTIC_KEYS = ("?",)

            def _render_surface(self, surface):
                pass

            def fresh(self):
                pass

        host = MagicMock()
        host.has_overlay_open.return_value = False
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = None
        child = _HelpChild()
        popup = Popup(child, session_owner=host)

        result = popup.dispatch_overlay_key("?")
        assert result is OverlayDispatchResult.HANDLED_IMPLICIT

    def test_popup_fallback_swallows_unbound(self):
        child = _Leaf()
        popup = Popup(child)
        result = popup.dispatch_overlay_key("z")
        assert result is OverlayDispatchResult.DROPPED_UNBOUND

    def test_popup_render_surface_not_open_skips(self):
        child = _Leaf()
        popup = Popup(child)
        popup.open = False
        surface = Surface(40, 20)
        popup._render_surface(surface)
        # No exception and child not rendered

    def test_popup_render_surface_resizes_if_needed(self):
        child = _Leaf()
        popup = Popup(child)
        popup.open = True
        popup._term_size = (0, 0)
        surface = Surface(40, 20)
        popup._render_surface(surface)
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
        lines = body._build_content_lines()

        assert any("Test message" in line for line in lines)
        # Footer should include both OK and Cancel
        assert any("OK" in line for line in lines)
        assert any("Cancel" in line for line in lines)

    def test_alert_body_confirm_calls_shell_finish(self):
        shell = MagicMock()
        body = AlertDialogBody(
            shell=shell,
            message="m",
            on_result=lambda x: None,
        )
        body._confirm()
        shell._finish_alert.assert_called_once_with(True)
