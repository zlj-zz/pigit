from __future__ import annotations

import sys
import time
from collections.abc import Callable
from functools import wraps


def time_it(fn: Callable) -> Callable:
    """Print the overall running time after ``fn`` completes.

    Output stays on the ``# runtime: N seconds`` line; dimmed on a TTY.
    """

    @wraps(fn)
    def wrap(*args, **kwargs):
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            msg = f"# runtime: {time.perf_counter() - start:.2f} seconds"
            if sys.stdout.isatty():
                msg = f"\033[2m{msg}\033[0m"
            print(f"\n{msg}")

    return wrap
