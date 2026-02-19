"""TagPrefixFilter configuration and helper functions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.filter.filter import Filter, HandlerTarget


class TagPrefixFilter(Filter):
    """Filter that passes when the target entity has at least one tag with the given prefix.

    Tags sharing a prefix (e.g., "team:red", "team:blue") are collected into a mask.
    The filter passes when the entity has any tag from that mask.

    Example:
        TagPrefixFilter(target=HandlerTarget.TARGET, tag_prefix="team")
    """

    filter_type: Literal["tag_prefix"] = "tag_prefix"
    target: HandlerTarget = Field(description="Entity to check the filter against")
    tag_prefix: str = Field(description="Tag prefix to match (e.g., 'team' matches 'team:red', 'team:blue')")


def hasTagPrefix(prefix: str, target: HandlerTarget = HandlerTarget.TARGET) -> TagPrefixFilter:
    """Filter: entity has at least one tag with the given prefix."""
    return TagPrefixFilter(target=target, tag_prefix=prefix)
