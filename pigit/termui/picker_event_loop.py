# -*- coding: utf-8 -*-
"""
Module: pigit/termui/picker_event_loop.py
Description: AppEventLoop variant for full-screen pickers that return (exit_code, message).
Author: Zev
Date: 2026-03-29
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from pigit.termui.event_loop import AppEventLoop, ExitEventLoop


class PickerAppEventLoop(AppEventLoop):
    """
    Event loop for :class:`~pigit.termui.component_list_picker.SearchableListPicker`.

    Re-raises :exc:`ExitEventLoop` after cleanup so callers can map to
    ``(exit_code, message)``. Runs only inside a real TTY :class:`Session`.
    """

    def _run_impl(self) -> None:
        try:
            self.start()
            self._loop()
        except ExitEventLoop:
            self.stop()
            raise
        except KeyboardInterrupt:
            self.stop()
            raise
        except EOFError:
            self.stop()
            raise
        except Exception as e:
            self.stop()
            logging.getLogger().exception(
                "PickerAppEventLoop: unhandled exception in main loop: %s", e
            )

    def run_with_result(self) -> tuple[int, Optional[str]]:
        """
        Same as :meth:`AppEventLoop.run` (``Session`` + ``self._alt`` + renderer bind),
        but map normal picker exit to ``(exit_code, message)`` via re-raised :exc:`ExitEventLoop`.
        """

        from pigit.termui._picker import PICK_EXIT_CTRL_C

        try:
            super().run()
        except ExitEventLoop as e:
            return e.exit_code, e.result_message
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            sys.stdout.flush()
            return PICK_EXIT_CTRL_C, None
        return 0, None
