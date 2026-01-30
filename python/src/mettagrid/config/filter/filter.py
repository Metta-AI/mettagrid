"""Base filter configuration and common types."""

from __future__ import annotations

from enum import StrEnum, auto
from typing import TYPE_CHECKING, Annotated, Union

from pydantic import Discriminator, Field, Tag

from mettagrid.base_config import Config

if TYPE_CHECKING:
    from mettagrid.config.filter.alignment_filter import AlignmentFilter
    from mettagrid.config.filter.game_value_filter import GameValueFilter
    from mettagrid.config.filter.near_filter import NearFilter
    from mettagrid.config.filter.resource_filter import ResourceFilter
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


AnyFilter = Annotated[
    Union[
        Annotated["VibeFilter", Tag("vibe")],
        Annotated["ResourceFilter", Tag("resource")],
        Annotated["AlignmentFilter", Tag("alignment")],
        Annotated["TagFilter", Tag("tag")],
        Annotated["NearFilter", Tag("near")],
        Annotated["GameValueFilter", Tag("game_value")],
    ],
    Discriminator("filter_type"),
]
