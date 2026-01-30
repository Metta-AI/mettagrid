"""Resource filter configuration and helper functions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.filter.filter import Filter, HandlerTarget


class ResourceFilter(Filter):
    """Filter that checks if the target entity has required resources."""

    filter_type: Literal["resource"] = "resource"
    resources: dict[str, int] = Field(
        default_factory=dict,
        description="Minimum resource amounts required",
    )


# ===== Helper Filter Functions =====


def actorHas(resources: dict[str, int]) -> ResourceFilter:
    """Filter: actor has at least the specified resources."""
    return ResourceFilter(target=HandlerTarget.ACTOR, resources=resources)


def targetHas(resources: dict[str, int]) -> ResourceFilter:
    """Filter: target has at least the specified resources."""
    return ResourceFilter(target=HandlerTarget.TARGET, resources=resources)


def actorCollectiveHas(resources: dict[str, int]) -> ResourceFilter:
    """Filter: actor's collective has at least the specified resources."""
    return ResourceFilter(target=HandlerTarget.ACTOR_COLLECTIVE, resources=resources)


def targetCollectiveHas(resources: dict[str, int]) -> ResourceFilter:
    """Filter: target's collective has at least the specified resources."""
    return ResourceFilter(target=HandlerTarget.TARGET_COLLECTIVE, resources=resources)
