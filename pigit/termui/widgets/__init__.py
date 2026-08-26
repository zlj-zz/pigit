"""
Package: pigit.termui.widgets
Description: Widget components for the TUI framework.

Usage:
    from pigit.termui.widgets import TextBrowser, BorderedTextBrowser, OptionList
"""

from __future__ import annotations

from .bordered_text_browser import BorderedTextBrowser
from .check_list import CheckList
from .command_palette import CommandPalette, PaletteItem, list_slots_for_term
from .footer import Footer
from .graph import HeatmapGrid, StepLineChart
from .header import Header
from .help_panel import HelpEntry, HelpPanel
from .input_line import InputLine
from .option_list import OptionList
from .label import Label
from .text_browser import TextBrowser
from .lint_bar import LintBar
from .popup import AlertDialog, AlertDialogBody, Popup
from .sheet import Sheet
from .shortcut_hints import ShortcutHints, measure_shortcut_hints, paint_shortcut_hints
from .static_list import StaticList
from .status_bar import StatusBar
from .toast import Toast

__all__ = [
    "BorderedTextBrowser",
    "AlertDialog",
    "AlertDialogBody",
    "CommandPalette",
    "PaletteItem",
    "list_slots_for_term",
    "Footer",
    "HeatmapGrid",
    "Header",
    "HelpEntry",
    "HelpPanel",
    "InputLine",
    "OptionList",
    "CheckList",
    "Label",
    "TextBrowser",
    "LintBar",
    "Popup",
    "Sheet",
    "ShortcutHints",
    "measure_shortcut_hints",
    "paint_shortcut_hints",
    "StaticList",
    "StatusBar",
    "StepLineChart",
    "Toast",
]
