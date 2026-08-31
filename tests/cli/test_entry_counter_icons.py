# -*- coding: utf-8 -*-
"""
Module: tests/cli/test_entry_counter_icons.py
Description: CLI counter icon rendering wires config.app.icons → resolve_icon.
Author: Zev
Date: 2026-08-29
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pigit.entry import pigit
from pigit.ext.utils import resolve_icon


def _config(*, icons: str) -> SimpleNamespace:
    return SimpleNamespace(
        counter=SimpleNamespace(
            format="table",
            show_icon=True,
            show_invalid=False,
            use_gitignore=False,
        ),
        repo=SimpleNamespace(auto_append=False),
        app=SimpleNamespace(icons=icons),
    )


def _run_count(icons: str) -> list[str]:
    """Run the counter table branch and return the echoed strings."""
    ctx = SimpleNamespace(config=MagicMock(), git_api=MagicMock())
    ctx.config.get.return_value = _config(icons=icons)
    ctx.git_api.confirm_repo.return_value = ("", "")
    echo = MagicMock()
    counter = MagicMock()
    counter.diff_count.return_value = (
        0,
        {"Python": {"1": 1, "2": 1, "3": 1, "4": 1}},
        [],
    )
    with (
        patch("pigit.entry.ctx", ctx),
        patch("pigit.termui.cli_output.get_console", return_value=MagicMock(echo=echo)),
        patch("pigit.ext.lcstat.Counter", return_value=counter),
    ):
        pigit.main(["--count", "."])
    return [c.args[0] for c in echo.call_args_list if c.args]


def test_counter_fallback_symbol_when_icons_off() -> None:
    texts = _run_count(icons="off")
    joined = "\n".join(texts)
    assert resolve_icon(False, "Python") in joined
    assert "Python" in joined


def test_counter_nerd_glyph_when_icons_on() -> None:
    texts = _run_count(icons="on")
    joined = "\n".join(texts)
    assert resolve_icon(True, "Python") in joined
