# -*- coding:utf-8 -*-
"""
Module: pigit/ext/log.py
Description: Root logging setup, named loggers, and uncaught-exception forwarding.
Author: Zev
Date: 2024-01-01
"""

import logging
import logging.handlers
import os
import sys
import threading
from typing import Optional

_PIGIT_HANDLER_ATTR = "_pigit_log_handler"
_UNCAUGHT_HOOKS_INSTALLED = False

FMT_NORMAL = logging.Formatter(
    fmt="%(asctime)s %(levelname).4s %(message)s", datefmt="%H:%M:%S"
)

FMT_DEBUG = logging.Formatter(
    fmt=(
        "%(asctime)s.%(msecs)03d %(levelname).4s [%(name)s] "
        "%(pathname)s:%(lineno)d %(message)s"
    ),
    datefmt="%H:%M:%S",
)


def _remove_pigit_handlers(root_logger: logging.Logger) -> None:
    """Drop handlers previously added by :func:`setup_logging` (safe repeat bootstrap)."""
    stale = [h for h in root_logger.handlers if getattr(h, _PIGIT_HANDLER_ATTR, False)]
    for handler in stale:
        root_logger.removeHandler(handler)
        handler.close()


def setup_logging(debug: bool = False, log_file: Optional[str] = None) -> None:
    """Configure the root logger and install uncaught-exception logging once."""

    # logging.getLogger() with no args returns the root logger (global parent of all loggers)
    # All custom loggers (e.g. logger("pigit")) inherit configuration from the root logger
    root_logger = logging.getLogger()
    _remove_pigit_handlers(root_logger)

    if debug:
        log_level = logging.DEBUG
        formatter = FMT_DEBUG
    else:
        log_level = logging.INFO
        formatter = FMT_NORMAL

    if log_file is None:
        log_handle: logging.Handler = logging.StreamHandler()
    else:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        try:
            log_handle = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=1048576, backupCount=4
            )
        except PermissionError:
            print("No permission to write to '{0}' directory!".format(log_file))
            raise SystemExit(1) from None

    log_handle.setFormatter(formatter)
    log_handle.setLevel(log_level)
    setattr(log_handle, _PIGIT_HANDLER_ATTR, True)

    root_logger.addHandler(log_handle)
    root_logger.setLevel(0)

    install_uncaught_exception_logging()


def install_uncaught_exception_logging() -> None:
    """Send uncaught exceptions through the root logger (same handlers as ``setup_logging``).

    Idempotent: only wraps ``sys.excepthook`` / ``threading.excepthook`` once per process.
    """

    global _UNCAUGHT_HOOKS_INSTALLED
    if _UNCAUGHT_HOOKS_INSTALLED:
        return
    _UNCAUGHT_HOOKS_INSTALLED = True

    _sys_hook = sys.excepthook

    def _excepthook(
        exc_type: type,
        exc_value: BaseException,
        exc_tb: Optional[object],
    ) -> None:
        logging.getLogger().error(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        _sys_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook

    if hasattr(threading, "excepthook"):
        _thread_hook = threading.excepthook

        def _thread_excepthook(args) -> None:
            logging.getLogger().error(
                "Uncaught exception in thread %r",
                args.thread.name,
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            _thread_hook(args)

        threading.excepthook = _thread_excepthook


# cache logger, avoid creating loggers with the same name repeatedly.
_logger_cache: dict[str, "logging.Logger"] = {}


def logger(name: Optional[str] = None) -> "logging.Logger":
    # not cache no name logger
    if name is None:
        return logging.getLogger()

    cache_logger = _logger_cache.get(name)
    if cache_logger is not None:
        return cache_logger

    new_logger = _logger_cache[name] = logging.getLogger(name)
    return new_logger
