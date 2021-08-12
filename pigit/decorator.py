# -*- coding:utf-8 -*-

from __future__ import print_function
import time
from functools import wraps


def time_it(fn):
    """Print the overall running time.
    When recursive calls exist, only the outermost layer is printed.
    """
    time_it.deep = 0

    @wraps(fn)
    def wrap_(*args, **kwargs):
        time_it.deep += 1
        start_time = time.time()
        res = None
        try:
            res = fn(*args, **kwargs)
        except SystemExit:
            pass
        time_it.deep -= 1
        if time_it.deep == 0:
            print("\nruntime: %fs" % (time.time() - start_time))
        return res

    return wrap_
