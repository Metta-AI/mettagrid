"""Resource filter configuration and helper functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import Field

if TYPE_CHECKING:
    from mettagrid.config.filter.filter import Filter, HandlerTarget, OrFilter
else:
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


def actorHasAnyOf(resources: list[str]) -> OrFilter:
    """Filter: actor has at least 1 of ANY of the specified resources.

    This is a convenience filter that creates an OR of multiple single-resource filters.
    Passes if the actor has at least 1 of ANY listed resource.

    Args:
        resources: List of resource names to check

    Returns:
        OrFilter that passes if actor has any of the resources
    """
    # Import here to avoid circular import at module load time
    from mettagrid.config.filter.filter import OrFilter as _OrFilter  # noqa: PLC0415

    return _OrFilter(inner=[ResourceFilter(target=HandlerTarget.ACTOR, resources={r: 1}) for r in resources])


def targetHasAnyOf(resources: list[str]) -> OrFilter:
    """Filter: target has at least 1 of ANY of the specified resources.

    This is a convenience filter that creates an OR of multiple single-resource filters.
    Passes if the target has at least 1 of ANY listed resource.

    Args:
        resources: List of resource names to check

    Returns:
        OrFilter that passes if target has any of the resources
    """
    # Import here to avoid circular import at module load time
    from mettagrid.config.filter.filter import OrFilter as _OrFilter  # noqa: PLC0415

    return _OrFilter(inner=[ResourceFilter(target=HandlerTarget.TARGET, resources={r: 1}) for r in resources])
