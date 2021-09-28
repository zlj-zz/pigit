from pyinstrument import Profiler
from functools import wraps


def analyze_it(fn):
    def inner(*args, **kwargs):
        profiler = Profiler()

        with profiler:
            res = fn(*args, **kwargs)
        profiler.print()
        return res

    return inner
