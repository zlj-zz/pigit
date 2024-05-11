import sys
from typing import List, Optional

from pigit.entry import pigit
from pigit.ext.func import time_it


@time_it
def _active(prefixes:Optional[List] = None):
    try:
        _args = (prefixes or []) + sys.argv[1:]
        pigit(_args)
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(0) from None


# =============================================
# terminal entry
# =============================================
main = lambda :_active()
g = lambda :_active(["cmd"])
r = lambda :_active(["repo"])
