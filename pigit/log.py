# -*- coding:utf-8 -*-

import os
import logging
import logging.handlers
from typing import Optional


FMT_NORMAL = logging.Formatter(
    fmt="%(asctime)s %(levelname).4s %(message)s", datefmt="%H:%M:%S"
)

FMT_DEBUG = logging.Formatter(
    fmt="%(asctime)s.%(msecs)03d %(levelname).4s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)


def setup_logging(debug: bool = False, log_file: Optional[str] = None):
    root_logger = logging.getLogger()
    # print(log_file)

    if debug:
        log_level = logging.DEBUG
        formatter = FMT_DEBUG
    else:
        log_level = logging.INFO
        formatter = FMT_NORMAL

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
