"""
Package: pigit.termui.widgets
Description: Widget components for the TUI framework.

Usage:
    from pigit.termui.widgets import TextBrowser, BorderedTextBrowser, OptionList
"""

from __future__ import annotations

from .bordered_text_browser import BorderedTextBrowser
from .check_list import CheckList
from .command_palette import (
    CommandPalette,
    PaletteArgs,
    PaletteItem,
    list_slots_for_term,
)
from .footer import Footer
from .graph import HeatmapGrid, StepLineChart
from .header import Header
from .help_format import format_binding_group_rows
from .help_panel import HelpEntry, HelpPanel, wrap_text
from .binding_browser import BindingBrowser
from .input_line import InputLine
from .option_list import ACCENT_BAR, OptionList
from .section_rule import SectionRule
from .label import Label
from .text_browser import TextBrowser, block_inset_for
from .lint_bar import LintBar
from .popup import AlertDialog, AlertDialogBody, Popup
from .repo_slot import RepoSlot
from .sheet import Sheet
from .shortcut_hints import ShortcutHints, measure_shortcut_hints, paint_shortcut_hints
from .static_list import StaticList
from .status_bar import StatusBar
from .header_slot import HeaderSlot
from .tab_slot import TabSlot
from .toast import Toast

__all__ = [
    "BorderedTextBrowser",
    "AlertDialog",
    "AlertDialogBody",
    "CommandPalette",
    "PaletteArgs",
    "PaletteItem",
    "list_slots_for_term",
    "Footer",
    "HeatmapGrid",
    "Header",
    "HelpEntry",
    "HelpPanel",
    "wrap_text",
    "format_binding_group_rows",
    "BindingBrowser",
    "InputLine",
    "OptionList",
    "ACCENT_BAR",
    "SectionRule",
    "CheckList",
    "Label",
    "TextBrowser",
    "block_inset_for",
    "LintBar",
    "Popup",
    "HeaderSlot",
    "RepoSlot",
    "Sheet",
    "ShortcutHints",
    "measure_shortcut_hints",
    "paint_shortcut_hints",
    "StaticList",
    "StatusBar",
    "StepLineChart",
    "TabSlot",
    "Toast",
]
