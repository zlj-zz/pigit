# -*- coding:utf-8 -*-

import datetime
import os
import platform


__project__ = "pigit"
__version__ = "1.7.1-dev"
__url__ = "https://github.com/zlj-zz/pigit.git"
__uri__ = __url__

__author__ = "Zachary Zhang"
__email__ = "zlj19971222@outlook.com"

__license__ = "MIT"
__copyright__ = f"Copyright (c) 2021-{datetime.datetime.now().year} Zachary"

# =========================================================
# Part of compatibility.
# Handled the incompatibility between python2 and python3.
# =========================================================
VERSION = __version__

IS_WIN: bool = platform.system() == "Windows"

# For windows should have a different home path.
USER_HOME: str = ""
PIGIT_HOME: str = ""
if IS_WIN:
    USER_HOME = os.environ["USERPROFILE"]
    PIGIT_HOME = os.path.join(USER_HOME, __project__)
else:
    # ~/.config/pigit
    USER_HOME = os.environ["HOME"]
    PIGIT_HOME = os.path.join(USER_HOME, ".config", __project__)

# Log file path
LOG_FILE_PATH: str = f"{PIGIT_HOME}/log/{__project__}.log"

# Config file path
CONFIG_FILE_PATH: str = f"{PIGIT_HOME}/pigit.conf"

# Code counter file path
COUNTER_DIR_PATH: str = f"{PIGIT_HOME}/Counter"

# User custom cmd path
EXTRA_CMD_MODULE_NAME: str = "extra_cmds"
EXTRA_CMD_MODULE_PATH: str = f"{PIGIT_HOME}/{EXTRA_CMD_MODULE_NAME}.py"

# Multi repos config file
REPOS_PATH: str = f"{PIGIT_HOME}/repos.json"

# Flag of first running
IS_FIRST_RUN: bool = not os.path.isdir(PIGIT_HOME)
if IS_FIRST_RUN:
    os.makedirs(PIGIT_HOME, exist_ok=True)
