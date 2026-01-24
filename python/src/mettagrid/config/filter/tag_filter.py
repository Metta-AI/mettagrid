"""Tag filter configuration and helper functions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.filter.filter import Filter, HandlerTarget


class TagFilter(Filter):
    """Filter that checks if the target has a specific tag.

    Tags are specified in "name:value" format (e.g., "type:assembler").
    This is useful for events that should only affect certain object types.

    Example:
        TagFilter(tag="type:assembler")  # only affects objects with "type:assembler" tag
    """

    filter_type: Literal["tag"] = "tag"
    tag: str = Field(description="Full tag in name:value format")


# ===== Helper Functions =====


def typeTag(name: str) -> str:
    """Return the type tag string for an object/agent name.

    Auto-generated type tags use this format. Objects named "wall" get tag "type:wall".

    Args:
        name: The object or agent type name (e.g., "wall", "agent", "assembler")
    """
    return f"type:{name}"


# ===== Helper Filter Functions =====


def hasTag(tag: str) -> TagFilter:
    """Filter: target has the specified tag.

    Args:
        tag: Full tag in name:value format (e.g., "type:assembler")
    """
    return TagFilter(target=HandlerTarget.TARGET, tag=tag)


def isA(type_value: str) -> TagFilter:
    """Filter: target has a type tag with the specified value.

    This is a convenience wrapper that creates hasTag(typeTag(type_value)).

    Args:
        type_value: The value for the type tag (e.g., "assembler", "junction")
    """
    return hasTag(typeTag(type_value))
