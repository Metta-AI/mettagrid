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
    return int(round(value))


def oc_equals(a, b) -> bool:
    return a == b


def oc_metta_sample(lower_limit, upper_limit, center, *, root=None):
    """
    Generates a value from a parameterized distribution centered around a specified point.

    This function returns values based on a "sampling" parameter that controls how widely
    the distribution spreads between the limiting values.

    Parameters:
    -----------
    lower_limit : numeric
        The minimum allowed value (lower boundary).
    upper_limit : numeric
        The maximum allowed value (upper boundary).
    center : numeric
        The center point of the distribution. When sampling=0, this value is returned directly.
    root : dict, optional
        A dictionary containing the "sampling" parameter. If None, sampling defaults to 0.

    Returns:
    --------
    numeric
        A value between lower_limit and upper_limit, with distribution controlled by the sampling parameter.
        Returns integer if center is an integer, float otherwise.

    Notes:
    ------
    - When sampling = 0: Returns exactly the center value.
    - When 0 < sampling <= 1: Returns a value from a scaled range around the center point.
    - When sampling > 1: Returns a value over [lower_limit, upper_limit] biased to the limit points.
    - Note that the center of the distribution changes away from "center" as the "sampling" parameter changes.

    Examples:
    ---------
    For metta_sample(0, 10, 5):
        - With sampling = 0: Always returns 5
        - With sampling = 0.5: Returns a uniform random value in range [2.5, 7.5]
        - With sampling = 1.0: Returns a uniform random value in range [0, 10]
        - With sampling = 2.0: Returns a uniform random value in range [0, 10] (50%), 0 (25%), 10 (25%)

    For metta_sample(0, 5, 2):
        - With sampling = 0: Always returns 2
        - With sampling = 0.5: Returns a uniform random value in range [1, 3.5]
        - With sampling = 1.0: Returns a uniform random value in range [0, 5]
        - With sampling = 10.0: Returns a uniform random value in range [0, 5] (10%), 0 (36%), 5 (54%)

    For metta_sample(0, 10, 8):
        - With sampling = 0: Always returns 8
        - With sampling = 0.5: Returns a uniform random value in range [4, 9]
        - With sampling = 1.0: Returns a uniform random value in range [0, 10]
    """
    # Get sampling parameter from root, defaulting to 0
    root = root or {}
    sampling = root.get("sampling", 0)

    # Fast path: return center when sampling is 0
    if sampling == 0:
        return center

    # Calculate the available range on both sides of the center
    left_range = center - lower_limit
    right_range = upper_limit - center

    # Scale the ranges based on the sampling parameter
    scaled_left = min(left_range, sampling * left_range)
    scaled_right = min(right_range, sampling * right_range)

    # Generate a random value within the scaled range
    val = np.random.uniform(center - scaled_left, center + scaled_right)

    # Clip to ensure we stay within [lower_limit, upper_limit]
    val = np.clip(val, lower_limit, upper_limit)

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
    OmegaConf.register_new_resolver("make_odd", oc_make_odd, replace=True)
    OmegaConf.register_new_resolver("clamp", oc_clamp, replace=True)
    OmegaConf.register_new_resolver("make_integer", oc_make_integer, replace=True)
    OmegaConf.register_new_resolver("int", oc_make_integer, replace=True)
    OmegaConf.register_new_resolver("equals", oc_equals, replace=True)
    OmegaConf.register_new_resolver("eq", oc_equals, replace=True)
    OmegaConf.register_new_resolver("metta_sample", oc_metta_sample, replace=True)
    OmegaConf.register_new_resolver("ms", oc_metta_sample, replace=True)
