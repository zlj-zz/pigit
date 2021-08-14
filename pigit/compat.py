# -*- coding:utf-8 -*-

import os
import sys
import subprocess

PYTHON3 = sys.version_info > (3, 0)
if PYTHON3:
    input = input
    range = range
    B = lambda x: x.encode("iso8859-1")  # noqa: E731

    import urllib.request

    urlopen = urllib.request.urlopen

    def get_terminal_size(fallback=(80, 24)):
        # fork from shutil.get_terminal_size()
        # columns, lines are the working values
        try:
            columns = int(os.environ["COLUMNS"])
        except (KeyError, ValueError):
            columns = 0

        try:
            lines = int(os.environ["LINES"])
        except (KeyError, ValueError):
            lines = 0

        # only query if necessary
        if columns <= 0 or lines <= 0:
            try:
                size = os.get_terminal_size(sys.__stdout__.fileno())
            except (AttributeError, ValueError, OSError):
                # stdout is None, closed, detached, or not a terminal, or
                # os.get_terminal_size() is unsupported
                size = fallback
            if columns <= 0:
                columns = size[0]
            if lines <= 0:
                lines = size[1]

        return columns, lines


else:
    input = raw_input
    range = xrange
    B = lambda x: x  # noqa: E731

    import urllib2

    urlopen = urllib2.urlopen

    def get_terminal_size(fallback=(80, 24)):
        # reason: python2 not support get_terminal_size().
        # columns, lines are the working values
        try:
            columns = int(os.environ["COLUMNS"])
        except (KeyError, ValueError):
            columns = 0

        try:
            lines = int(os.environ["LINES"])
        except (KeyError, ValueError):
            lines = 0

        # only query if necessary
        if columns <= 0 or lines <= 0:
            try:
                size = subprocess.check_output(["stty", "size"]).split()
                size = [int(i) for i in size[::-1]]
            except (AttributeError, ValueError, OSError):
                size = fallback
            if columns <= 0:
                columns = size[0]
            if lines <= 0:
                lines = size[1]

        return columns, lines
