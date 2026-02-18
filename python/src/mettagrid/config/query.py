"""Query type for finding objects by tag with optional filters."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import Field

from mettagrid.base_config import Config
from mettagrid.config.tag import Tag

if TYPE_CHECKING:
    from mettagrid.config.filter import AnyFilter


class Query(Config):
    """A query that finds objects by tag with optional filters.

    Used for efficient spatial lookup via TagIndex. The tag identifies candidate
    objects, and the filters narrow the results.
    """

    tag: Tag = Field(description="Tag for efficient spatial lookup via TagIndex")
    filters: Sequence["AnyFilter"] = Field(
        default_factory=list,
        description="Filters that matched objects must pass (all must match)",
    )


def query(tag: str | Tag, filters: list[AnyFilter] | None = None) -> Query:
    """Create a Query for finding objects by tag with optional filters.

    Args:
        tag: Tag name (str) or Tag instance for efficient spatial lookup
        filters: Additional filters that matched objects must pass

    Examples:
        query("type:junction")
        query("type:agent", [hasTag(tag("collective:cogs"))])
    """
    if isinstance(tag, str):
        tag = Tag(name=tag)
    return Query(tag=tag, filters=filters or [])
