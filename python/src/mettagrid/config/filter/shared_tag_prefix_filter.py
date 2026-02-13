"""SharedTagPrefixFilter configuration and helper functions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.base_config import Config


class SharedTagPrefixFilter(Config):
    """Filter that passes when actor and target share at least one tag with the given prefix.

    Unlike single-entity filters, this always compares actor vs target.
    Tags sharing a prefix (e.g., "team:red", "team:blue") are collected into a mask.
    The filter passes when actor and target have any overlapping tags from that mask.

    Example:
        SharedTagPrefixFilter(tag_prefix="team")
    """

    filter_type: Literal["shared_tag_prefix"] = "shared_tag_prefix"
    tag_prefix: str = Field(description="Tag prefix to match (e.g., 'team' matches 'team:red', 'team:blue')")


def sharedTagPrefix(prefix: str) -> SharedTagPrefixFilter:
    """Filter: actor and target share at least one tag with the given prefix."""
    return SharedTagPrefixFilter(tag_prefix=prefix)
