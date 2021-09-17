# -*- coding:utf-8 -*-

import time
from functools import wraps


def time_it(fn):
    """Print the overall running time.
    When recursive calls exist, only the outermost layer is printed.
    """
    time_it.deep = 0  # Mark recursion levels.
    time_unit = ["second", "mintue", "hour"]

    @wraps(fn)
    def wrap_(*args, **kwargs):
        time_it.deep += 1
        start_time = time.time()
        res = None
        try:
            res = fn(*args, **kwargs)
        except (SystemExit, EOFError):
            pass
        time_it.deep -= 1

        # Indicates that the decorated method does not or end a recursive call.
        if time_it.deep == 0:
            used_time = time.time() - start_time

            # Do unit optimization.
            for i in range(2):
                if used_time >= 60:
                    used_time /= 60
                else:
                    break
            else:
                i = 2
            print("\nruntime: {0:.2f} {1}".format(used_time, time_unit[i]))
        return res

    return wrap_
