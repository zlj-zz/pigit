from __future__ import annotations

import sys

from pigit.entry import pigit
from pigit.ext.func import time_it


@time_it
def _active(prefixes: list | None = None):
    try:
        _args = (prefixes or []) + sys.argv[1:]
        pigit(_args)
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(0) from None


# =============================================
# terminal entry
# =============================================
main = lambda: _active()
g = lambda: _active(["cmd"])
r = lambda: _active(["repo"])
