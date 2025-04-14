import random
from typing import Any

import numpy as np
from omegaconf import OmegaConf

def oc_if(condition, true_value, false_value):
    return true_value if condition else false_value


def oc_uniform(min_val: float, max_val: float) -> float:
    return float(np.random.uniform(min_val, max_val))


def oc_choose(*args: Any) -> Any:
    return random.choice(args)


def oc_divide(a: float, b: float) -> float:
    return a / b


def oc_subtract(a: float, b: float) -> float:
    return a - b


def oc_multiply(a: float, b: float) -> float:
    return a * b


def oc_add(a: float, b: float) -> float:
    return a + b


def oc_make_odd(a: float) -> int:
    """
    Ensure a value is odd and at least 3.
    """
    return max(3, int(a) // 2 * 2 + 1)


def oc_clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


def oc_make_integer(value: float) -> int:
    """
    Convert a float value to the nearest integer.
    """
    return int(round(value))


def register_resolvers():
    """
    Register all OmegaConf resolvers defined in this module.
    This function should be called before using any configuration that depends on these resolvers.
    """
    OmegaConf.register_new_resolver("if", oc_if, replace=True)
    OmegaConf.register_new_resolver("uniform", oc_uniform, replace=True)
    OmegaConf.register_new_resolver("choose", oc_choose, replace=True)
    OmegaConf.register_new_resolver("div", oc_divide, replace=True)
    OmegaConf.register_new_resolver("subtract", oc_subtract, replace=True)
    OmegaConf.register_new_resolver("sub", oc_subtract, replace=True)
    OmegaConf.register_new_resolver("multiply", oc_multiply, replace=True)
    OmegaConf.register_new_resolver("mul", oc_multiply, replace=True)
    OmegaConf.register_new_resolver("add", oc_add, replace=True)
    OmegaConf.register_new_resolver("make_odd", oc_make_odd, replace=True)
    OmegaConf.register_new_resolver("clamp", oc_clamp, replace=True)
    OmegaConf.register_new_resolver("make_integer", oc_make_integer, replace=True)
    OmegaConf.register_new_resolver("int", oc_make_integer, replace=True)
