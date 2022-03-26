from typing import Optional
import pytest
import doctest

from pigit.interaction import StatusPanel, BranchPanel, FilePanel
import shutil


def test():
    print()

    size = shutil.get_terminal_size()
    panel = StatusPanel(widget=FilePanel())
    panel._render(size)

    branch_panel = BranchPanel()
