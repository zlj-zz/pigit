# -*- coding:utf-8 -*-

import os
import logging
import logging.handlers


class LogHandle(object):
    """Set log handle.
    Attributes:
        FMT_NORMAL: Log style in normal mode.
        FMT_DEBUG: Log style in debug mode.

    Functions:
        setup_logging: setup log handle setting.

    Raises:
        SystemExit: When the log file cannot be written.
    """

    FMT_NORMAL = logging.Formatter(
        fmt="%(asctime)s %(levelname).4s %(message)s", datefmt="%H:%M:%S"
    )
    FMT_DEBUG = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d %(levelname).4s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    @classmethod
    def setup_logging(cls, debug=False, log_file=None):
        root_logger = logging.getLogger()

        if debug:
            log_level = logging.DEBUG
            formatter = cls.FMT_DEBUG
        else:
            log_level = logging.INFO
            formatter = cls.FMT_NORMAL

        if log_file:
            if log_file is None:
                log_handle = logging.StreamHandler()
            else:
                dir_path = os.path.dirname(log_file)
                if not os.path.isdir(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                try:
                    log_handle = logging.handlers.RotatingFileHandler(
                        log_file, maxBytes=1048576, backupCount=4
                    )
                except PermissionError:
                    print("No permission to write to '{0}' directory!".format(log_file))
                    raise SystemExit(1)

        log_handle.setFormatter(formatter)
        log_handle.setLevel(log_level)

        root_logger.addHandler(log_handle)
        root_logger.setLevel(0)
