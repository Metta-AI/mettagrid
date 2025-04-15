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


def oc_to_odd_min3(a: float) -> int:
    """
    Ensure a value is odd and at least 3.
    """
    return max(3, int(a) // 2 * 2 + 1)


def oc_clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


def oc_make_integer(value: float) -> int:
    return int(round(value))


def oc_equals(a, b) -> bool:
    return a == b


def oc_scaled_range(lower_limit, upper_limit, center, *, root=None):
    """
    Generates a value centered around a specified point based on a "sampling" parameter that controls how
    widely the distribution spreads between the limiting values.

    Parameters:
    -----------
    lower_limit : numeric
        The minimum allowed value (lower boundary).
    upper_limit : numeric
        The maximum allowed value (upper boundary).
    center : numeric
        The center point of the distribution. When sampling=0, this value is returned directly.
    root : dict, optional
        A dictionary containing the "sampling" parameter. If None, sampling defaults to 0. Must be between 0 and 1.

    Returns:
    --------
    numeric
        A value between lower_limit and upper_limit, with distribution controlled by the sampling parameter.
        Returns integer if center is an integer, float otherwise.

    """
    # Get sampling parameter from root, defaulting to 0
    root = root or {}
    sampling = root.get("sampling", 0)

    # Fast path: return center when sampling is 0
    if sampling == 0:
        return center

    assert sampling <= 1, 'Environment configuration for "sampling" must be in range [0, 1]!'

    # Calculate the scaled range on both sides of the center
    left_range = sampling * (center - lower_limit)
    right_range = sampling * (upper_limit - center)

    # Generate a random value within the scaled range
    val = np.random.uniform(center - left_range, center + right_range)

    # Return integer if the center was an integer
    return int(round(val)) if isinstance(center, int) else val


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
    OmegaConf.register_new_resolver("make_odd", oc_to_odd_min3, replace=True)
    OmegaConf.register_new_resolver("clamp", oc_clamp, replace=True)
    OmegaConf.register_new_resolver("make_integer", oc_make_integer, replace=True)
    OmegaConf.register_new_resolver("int", oc_make_integer, replace=True)
    OmegaConf.register_new_resolver("equals", oc_equals, replace=True)
    OmegaConf.register_new_resolver("eq", oc_equals, replace=True)
    OmegaConf.register_new_resolver("sampling", oc_scaled_range, replace=True)
