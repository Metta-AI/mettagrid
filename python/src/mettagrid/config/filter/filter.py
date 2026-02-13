"""Base filter configuration and common types."""

from __future__ import annotations

from enum import StrEnum, auto
from typing import TYPE_CHECKING, Annotated, Literal, Union

from pydantic import Discriminator, Field, Tag

from mettagrid.base_config import Config

if TYPE_CHECKING:
    from mettagrid.config.filter.alignment_filter import AlignmentFilter
    from mettagrid.config.filter.game_value_filter import GameValueFilter
    from mettagrid.config.filter.near_filter import NearFilter
    from mettagrid.config.filter.resource_filter import ResourceFilter
    from mettagrid.config.filter.shared_tag_prefix_filter import SharedTagPrefixFilter
    from mettagrid.config.filter.tag_filter import TagFilter
    from mettagrid.config.filter.vibe_filter import VibeFilter


class HandlerTarget(StrEnum):
    """Target entity for filter operations."""

    ACTOR = auto()
    TARGET = auto()
    ACTOR_COLLECTIVE = auto()
    TARGET_COLLECTIVE = auto()


class Filter(Config):
    """Base class for handler filters. All filters in a handler must pass."""

    target: HandlerTarget = Field(description="Entity to check the filter against")


class NotFilter(Config):
    """Wrapper filter that negates the result of an inner filter.

    Use isNot() helper function to create NotFilter instances.
    """

    filter_type: Literal["not"] = "not"
    inner: "AnyFilter" = Field(description="The filter to negate")


def isNot(filter: "AnyFilter") -> NotFilter:
    """Negate a filter. Returns a NotFilter that passes when the inner filter fails.

    Args:
        filter: Any filter to negate

    Returns:
        NotFilter wrapping the provided filter
    """
    return NotFilter(inner=filter)


class OrFilter(Config):
    """Wrapper filter that ORs multiple inner filters.

    Passes if ANY of the inner filters passes.
    Use anyOf() helper function to create OrFilter instances.
    """

    filter_type: Literal["or"] = "or"
    inner: list["AnyFilter"] = Field(description="The filters to OR together")


def anyOf(filters: list["AnyFilter"]) -> OrFilter:
    """Create an OR filter that passes if ANY inner filter passes.

    Args:
        filters: List of filters to OR together

    Returns:
        OrFilter wrapping the provided filters
    """
    return OrFilter(inner=filters)


AnyFilter = Annotated[
    Union[
        Annotated["VibeFilter", Tag("vibe")],
        Annotated["ResourceFilter", Tag("resource")],
        Annotated["AlignmentFilter", Tag("alignment")],
        Annotated["TagFilter", Tag("tag")],
        Annotated["SharedTagPrefixFilter", Tag("shared_tag_prefix")],
        Annotated["NearFilter", Tag("near")],
        Annotated["GameValueFilter", Tag("game_value")],
        Annotated["NotFilter", Tag("not")],
        Annotated["OrFilter", Tag("or")],
    ],
    Discriminator("filter_type"),
]

# NotFilter.model_rebuild() is called in __init__.py after all filter types are imported
