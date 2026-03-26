# -*- coding: utf-8 -*-
"""
Legacy full-screen TUI stack (components, event loop, console, input).

This package is **deprecated for new features**; prefer ``pigit.termui`` (see
CHANGELOG and ``docs/termui_testing.md``). It remains for compatibility; internal
modules such as ``pigit.tui.utils`` are still imported by ``pigit.termui.text``.

# tui structure:
# =========================================================================================
#     +----------------+                 +--------------+
#     |                |                 |              |
#     |                |---------------->|              |
#     |                |<----------------|    Input     |
#     |                |                 |              |
#     |                |                 |              |
#     |                |                 +--------------+
#     |      Main      |
#     |      Loop      |
#     |                |                 +--------------+                  +--------------+
#     |                |                 |              |                  |              |
#     |                |                 |              |                  |              |
#     |                |---------------->|    Screen    |----------------->|    Widget    |
#     |                |                 |              |                  |              |
#     |                |                 |              |                  |              |
#     |                |                 +--------------+                  +--------------+
#     |                |
#     +----------------+
"""
