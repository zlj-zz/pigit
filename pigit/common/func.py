from typing import Any, Callable
from functools import wraps
import inspect


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
