import functools
import inspect
import threading
from functools import wraps
from time import monotonic

DEBUG = False
TIME0 = monotonic()


def make_debugger(debug: bool):
    """Factory that returns a debug wrapper with the given enabled flag."""

    def _debugger(func):
        @wraps(func)
        def decorator(*args, **kwargs):
            if debug:
                self = args[0] if args else None
                timestamp = round(monotonic() - TIME0, 3)
                who = self.__class__.__name__ if self is not None else "<no-self>"
                print(f"{who}.{func.__name__} : {timestamp}")
            return func(*args, **kwargs)

        return decorator

    return _debugger


def debugger(_cls=None, *, debug: bool = DEBUG, include_private: bool = False):
    """Debugging decorator. Can be used at class or method level.

    Examples
    --------
    >>> @debugger
    >>> class MyClass:
    >>>     def method1(self):
    >>>         pass
    >>>     def method2(self):
    >>>         pass
    >>>
    >>> MyClass.method1 : <elapsed time since app start>
    >>> MyClass.method2 : <elapsed time since app start>
    >>>
    >>> class MyClass:
    >>>     def method1(self):
    >>>         pass
    >>>     @debugger
    >>>     def method2(self):
    >>>         pass
    >>>
    >>> MyClass.method2 : <elapsed time since app start>
    """

    def decorator(cls):
        _debugger = make_debugger(debug)
        if inspect.isfunction(cls):
            return _debugger(cls)
        for name, attr in list(cls.__dict__.items()):
            if not include_private and name.startswith("_"):
                continue
            if inspect.isfunction(attr):
                setattr(cls, name, _debugger(attr))
        return cls

    if _cls is not None:
        return decorator(_cls)

    return decorator


_thread_local = threading.local()


def per_thread_cache(func):
    """Decorator for per-thread caching of functions, methods, or properties."""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        cache = getattr(_thread_local, "cache", None)
        if cache is None:
            cache = {}
            _thread_local.cache = cache

        uuid_attr = getattr(self, f"{func.__name__}_uuid", None)
        key = (id(self), func, uuid_attr, args, frozenset(kwargs.items()))

        if key not in cache:
            cache[key] = func(self, *args, **kwargs)

        return cache[key]

    if isinstance(func, property):
        return property(wrapper)

    return wrapper
