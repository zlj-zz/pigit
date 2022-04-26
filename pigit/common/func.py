from typing import Any, Callable
from functools import wraps
import time, contextlib, inspect


def time_it(fn: Callable) -> Callable:
    """Print the overall running time.
    When recursive calls exist, only the outermost layer is printed.
    """
    time_it.deep = 0  # Mark recursion levels.
    time_unit = ["second", "mintue", "hour"]

    @wraps(fn)
    def wrap(*args, **kwargs):
        time_it.deep += 1
        start_time = time.time()
        res = None
        with contextlib.suppress(SystemExit, EOFError):
            res = fn(*args, **kwargs)
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

    return wrap


def dynamic_default_attrs(fn: Callable, **kwds: Any) -> Callable:
    """Set default parameters dynamically.

    Receive a method and several named parameters, which will be saved.
    When the method is called, it will be filled in automatically, and
    the incoming value will replace the dynamic default value. It can be
    used as a decorator.
    """

    _kwds = kwds
    _fn_params = list(inspect.signature(fn).parameters.keys())
    _fn_params_len = len(_fn_params)

    @wraps(fn)
    def wrap(*args, **kwargs) -> Any:
        final_kwargs = {**_kwds, **kwargs}
        args_len = len(args)

        if extra_len := (args_len + len(final_kwargs) - _fn_params_len) > 0:
            used_list = _fn_params[args_len - extra_len : args_len]
            for used in used_list:
                final_kwargs.pop(used)

        return fn(*args, **final_kwargs)

    return wrap
