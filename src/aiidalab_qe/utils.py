import inspect
import typing as t
from functools import wraps
from time import monotonic

from aiida import orm
from aiida.common.exceptions import NotExistent

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
        for name, attr in list(cls.__dict__.items()):
            if not include_private and name.startswith("_"):
                continue
            if inspect.isfunction(attr):
                setattr(cls, name, _debugger(attr))
        return cls

    if _cls is not None:
        return decorator(_cls)

    return decorator


def generate_alert(alert_type: str, message: str, class_: str = "", style_: str = ""):
    return f"""
        <div class="alert alert-{alert_type} warning-box {class_}" style="{style_}">
            {message}
        </div>
    """


def set_component_resources(component, code_info):
    """Set the resources for a given component based on the code info."""
    if code_info:  # Ensure code_info is not None or empty (# XXX: ? from jyu, need to pop a warning to plugin developer or what?)
        code: orm.Code = code_info["code"]
        if code.computer.scheduler_type == "hyperqueue":
            component.metadata.options.resources = {
                "num_cpus": code_info["nodes"]
                * code_info["ntasks_per_node"]
                * code_info["cpus_per_task"]
            }
        else:
            # XXX: jyu should properly deal with None type of scheduler_type which can be "core.direct" (will be replaced by hyperqueue) and "core.slurm" ...
            component.metadata.options.resources = {
                "num_machines": code_info["nodes"],
                "num_mpiprocs_per_machine": code_info["ntasks_per_node"],
                "num_cores_per_mpiproc": code_info["cpus_per_task"],
            }

        component.metadata.options["max_wallclock_seconds"] = code_info[
            "max_wallclock_seconds"
        ]
        if "parallelization" in code_info:
            component.parallelization = orm.Dict(dict=code_info["parallelization"])


def enable_pencil_decomposition(component):
    """Enable the pencil decomposition for the given component."""

    component.settings = orm.Dict({"CMDLINE": ["-pd", ".true."]})


def shallow_copy_nested_dict(d):
    """Recursively copies only the dictionary structure but keeps value references."""
    if isinstance(d, dict):
        return {key: shallow_copy_nested_dict(value) for key, value in d.items()}
    return d


def get_pseudo_info(pp_uuid) -> dict[str, t.Any]:
    try:
        pp_node = orm.load_node(pp_uuid)
    except NotExistent as err:
        raise ValueError(
            f"Pseudo potential with UUID {pp_uuid} does not exist"
        ) from err

    return {
        "functional": pp_node.base.extras.get("functional", None),
        "relativistic": pp_node.base.extras.get("relativistic", None),
    }
