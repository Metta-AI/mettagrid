"""Filter configuration classes and helper functions.

This module re-exports from mettagrid.config.filter for backwards compatibility.
"""

# Re-export everything from the filter subpackage
from mettagrid.config.filter import (
    AnyFilter,
    Filter,
    HandlerTarget,
    MaxDistanceFilter,
    NotFilter,
    ResourceFilter,
    TagFilter,
    VibeFilter,
    actorHas,
    hasTag,
    isA,
    isNear,
    isNot,
    targetHas,
)

__all__ = [
    # Enums
    "HandlerTarget",
    # Filter classes
    "Filter",
    "NotFilter",
    "VibeFilter",
    "ResourceFilter",
    "TagFilter",
    "MaxDistanceFilter",
    "AnyFilter",
    # Filter helpers
    "isNot",
    "hasTag",
    "isA",
    "isNear",
    "actorHas",
    "targetHas",
]
