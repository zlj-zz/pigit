# -*- coding: utf-8 -*-
"""
Module: pigit/interactive/__init__.py
Description: Public surface for TTY primitives, layout helpers, and list/repo pickers.
Author: Project Team
Date: 2026-03-23
"""

from .layout import (
    PICKER_FOOTER_ROWS,
    PICKER_HEADER_ROWS,
    picker_terminal_ok,
    picker_viewport,
)
from .list_picker import (
    PICK_EXIT_CTRL_C,
    PickerRow,
    apply_picker_filter,
    run_list_picker,
)
from .repo_cd import EMPTY_MANAGED_REPOS_MSG, run_repo_cd_picker
from .tty_primitives import (
    read_char_raw,
    read_line_cancellable,
    terminal_size,
    truncate_line,
    tty_ok,
)

__all__ = [
    "EMPTY_MANAGED_REPOS_MSG",
    "PICKER_FOOTER_ROWS",
    "PICKER_HEADER_ROWS",
    "PICK_EXIT_CTRL_C",
    "PickerRow",
    "apply_picker_filter",
    "picker_terminal_ok",
    "picker_viewport",
    "read_char_raw",
    "read_line_cancellable",
    "run_list_picker",
    "run_repo_cd_picker",
    "terminal_size",
    "truncate_line",
    "tty_ok",
]
