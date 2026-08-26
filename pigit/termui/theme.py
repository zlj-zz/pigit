"""
Module: pigit/termui/theme.py
Description: Semantic Theme tokens and ContextVar-based theme resolution for termui widgets.
Author: Zev
Date: 2026-08-19
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from . import palette


@dataclass(frozen=True)
class Theme:
    """Semantic color roles for termui widgets and syntax highlighting.

    Attributes:
        bg_base: Deepest background layer.
        bg_panel: Elevated panel background.
        bg_hover: Hover / cursor-row highlight background.
        bg_active: Active selection background.
        fg_primary: Primary foreground text.
        fg_muted: Muted foreground text.
        fg_dim: Dimmed foreground text (decor / chrome rules).
        fg_inactive: Structural text when a MODAL/SHEET steals presentation.
        fg_success: Success state foreground.
        fg_warning: Warning state foreground.
        fg_danger: Danger state foreground.
        fg_info: Informational foreground.
        bg_overlay: Overlay panel background.
        bg_chrome: Chrome bar background (status bar, input line).
        bg_diff_add: Diff added-line background.
        bg_diff_del: Diff deleted-line background.
        fg_diff_add: Diff added-line foreground.
        fg_diff_del: Diff deleted-line foreground.
        fg_syntax_keyword: Syntax keyword token color.
        fg_syntax_string: Syntax string token color.
        fg_syntax_comment: Syntax comment token color.
        fg_syntax_function: Syntax function/call token color.
        fg_syntax_number: Syntax number token color.
        fg_syntax_type: Syntax type token color.
    """

    bg_base: tuple[int, int, int] = palette.CHARCOAL
    bg_panel: tuple[int, int, int] = palette.GRAPHITE
    bg_hover: tuple[int, int, int] = palette.GUNMETAL
    bg_active: tuple[int, int, int] = palette.STEEL
    fg_primary: tuple[int, int, int] = palette.ALMOST_WHITE
    fg_muted: tuple[int, int, int] = palette.MUTED
    fg_dim: tuple[int, int, int] = palette.DIM
    fg_inactive: tuple[int, int, int] = palette.SLATE
    fg_panel_title: tuple[int, int, int] = palette.ALMOST_WHITE
    fg_success: tuple[int, int, int] = palette.GREEN
    fg_warning: tuple[int, int, int] = palette.YELLOW
    fg_danger: tuple[int, int, int] = palette.RED
    fg_info: tuple[int, int, int] = palette.BLUE
    bg_overlay: tuple[int, int, int] = palette.SLATE_DARK
    bg_chrome: tuple[int, int, int] = palette.INK
    # Brand interaction accent (cursor mark, footer keys, focused section rules).
    fg_accent: tuple[int, int, int] = palette.ACCENT
    bg_diff_add: tuple[int, int, int] = palette.FOREST
    bg_diff_del: tuple[int, int, int] = palette.MAROON
    fg_diff_add: tuple[int, int, int] = palette.GREEN
    fg_diff_del: tuple[int, int, int] = palette.RED
    fg_syntax_keyword: tuple[int, int, int] = palette.PURPLE
    fg_syntax_string: tuple[int, int, int] = palette.GREEN
    fg_syntax_comment: tuple[int, int, int] = palette.SLATE
    fg_syntax_function: tuple[int, int, int] = palette.BLUE
    fg_syntax_number: tuple[int, int, int] = palette.MAGENTA
    fg_syntax_type: tuple[int, int, int] = palette.CYAN


DEFAULT_THEME = Theme()
_theme_var: ContextVar[Theme] = ContextVar("termui_theme", default=DEFAULT_THEME)


def get_theme() -> Theme:
    """Return the active semantic theme for the current context.

    Returns:
        Theme: The theme bound to this context, or ``DEFAULT_THEME``.
    """
    return _theme_var.get()


def set_theme(theme: Theme) -> None:
    """Bind a theme for the current context.

    Args:
        theme: Theme instance to use for subsequent widget rendering.
    """
    _theme_var.set(theme)
