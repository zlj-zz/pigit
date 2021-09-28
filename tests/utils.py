from functools import wraps
from pyinstrument import Profiler


def analyze_it(fn):
    """Analysis of decorated methods."""

    @wraps(fn)
    def inner(*args, **kwargs):
        profiler = Profiler()

        with profiler:
            res = fn(*args, **kwargs)
        profiler.print()
        return res

    return inner
