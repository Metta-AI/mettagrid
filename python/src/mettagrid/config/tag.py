"""Tag helper functions for tag name construction."""


def tag(name: str) -> str:
    return name


def typeTag(name: str) -> str:
    """Return the type tag for an object/agent name.

    Auto-generated type tags use this format. Objects named "wall" get tag "type:wall".
    """
    return f"type:{name}"
