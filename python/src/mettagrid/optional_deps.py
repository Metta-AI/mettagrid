"""Dependency availability checks for optional extras."""

import importlib.util


def _is_importable(module_name: str) -> bool:
    """Check if a module can be imported without actually importing it."""
    return importlib.util.find_spec(module_name) is not None


def has_train() -> bool:
    """Return True if the ``train`` extra (PyTorch + PufferLib) is installed."""
    return _is_importable("torch") and _is_importable("pufferlib")


def require_train(context: str) -> None:
    """Raise a clear error if the ``train`` extra is not installed.

    Args:
        context: Description of what triggered the check, shown in the
            error message so users know why it failed.
    """
    if has_train():
        return
    raise ImportError(
        f"'{context}' requires PyTorch and PufferLib, which are not installed.\n"
        "\n"
        "Install them with:\n"
        "  pip install mettagrid[train]"
    )
