# -*- coding:utf-8 -*-

import os, sys

__project__ = "pigit"
__version__ = "1.5.0"
__url__ = "https://github.com/zlj-zz/pigit.git"
__uri__ = __url__

__author__ = "Zachary Zhang"
__email__ = "zlj19971222@outlook.com"

__license__ = "MIT"
__copyright__ = "Copyright (c) 2021-2022 Zachary"

#####################################################################
# Part of compatibility.                                            #
# Handled the incompatibility between python2 and python3.          #
#####################################################################

# For windows.
USER_HOME: str = ""
PIGIT_HOME: str = ""
IS_WIN: bool = sys.platform.lower().startswith("win")

if IS_WIN:
    USER_HOME = os.environ["USERPROFILE"]
    PIGIT_HOME = os.path.join(USER_HOME, __project__)
else:
    # ~/.config/pigit
    USER_HOME = os.environ["HOME"]
    PIGIT_HOME = os.path.join(USER_HOME, ".config", __project__)

IS_FIRST_RUN: bool = not os.path.isdir(PIGIT_HOME)

LOG_FILE_PATH: str = PIGIT_HOME + "/log/{0}.log".format(__project__)

CONFIG_FILE_PATH: str = PIGIT_HOME + "/pigit.conf"

COUNTER_DIR_PATH: str = PIGIT_HOME + "/Counter"

EXTRA_CMD_FILE_PATH: str = PIGIT_HOME + "/extra_cmds.py"

REPOS_PATH: str = PIGIT_HOME + "/repos.json"

if IS_FIRST_RUN:
    os.makedirs(PIGIT_HOME, exist_ok=True)
