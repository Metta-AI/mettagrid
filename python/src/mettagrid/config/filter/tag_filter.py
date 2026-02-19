"""Tag filter configuration and helper functions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.filter.filter import Filter, HandlerTarget
from mettagrid.config.tag import typeTag


class TagFilter(Filter):
    """Filter that checks if the target has a specific tag.

    Tags are specified in "name:value" format (e.g., typeTag("hub")).
    This is useful for events that should only affect certain object types.

    Example:
        TagFilter(target=HandlerTarget.TARGET, tag=typeTag("hub"))
    """

    filter_type: Literal["tag"] = "tag"
    target: HandlerTarget = Field(description="Entity to check the filter against")
    tag: str = Field(description="Full tag in name:value format")


# ===== Helper Filter Functions =====


def hasTag(tag: str) -> TagFilter:
    """Filter: target has the specified tag.

    Args:
        tag: Full tag in name:value format (e.g., typeTag("hub"))
    """
    return TagFilter(target=HandlerTarget.TARGET, tag=tag)


def isA(type_value: str) -> TagFilter:
    """Filter: target has a type tag with the specified value.

    This is a convenience wrapper that creates hasTag(typeTag(type_value)).

    Args:
        type_value: The value for the type tag (e.g., "hub", "junction")
    """
    return hasTag(typeTag(type_value))
