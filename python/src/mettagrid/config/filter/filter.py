"""Base filter configuration and common types."""

from __future__ import annotations

from enum import StrEnum, auto
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from mettagrid.base_config import Config

if TYPE_CHECKING:
    from mettagrid.config.filter import AnyFilter


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
