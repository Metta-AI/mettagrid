"""Event configuration for timestep-based events.

Events allow applying mutations to filtered objects at specific timesteps.
This provides a declarative way to define game events like periodic effects,
timed triggers, or scripted scenarios.

Example:
    EventConfig(
        name="periodic_damage",
        target_tag="type:enemy",
        timesteps=periodic(start=100, period=50, end=1000),
        filters=[TagFilter(tag="type:enemy")],
        mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"hp": -10})]
    )
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from mettagrid.config.handler_config import Handler


def periodic(start: int, period: int, end: Optional[int] = None, end_period: Optional[int] = None) -> list[int]:
    """Generate periodic timesteps.

    Args:
        start: First timestep to fire
        period: Interval between firings (at start if end_period is set)
        end: Last timestep to fire (inclusive). If None, generates up to 100000.
        end_period: If set, interpolates the period from `period` to `end_period` over the
            start-end time range.

    Returns:
        List of timesteps
    """
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    if end is None:
        end = 100000
    if end_period is not None and end_period <= 0:
        raise ValueError(f"end_period must be positive, got {end_period}")

    if end_period is None:
        # Simple case: constant period
        return list(range(start, end + 1, period))

    # Interpolating period case
    timesteps = []
    t = start
    total_duration = end - start
    while t <= end:
        timesteps.append(t)
        if total_duration == 0:
            break
        # Calculate progress through the time range (0.0 to 1.0)
        progress = (t - start) / total_duration
        # Linearly interpolate between period and end_period
        current_period = period + progress * (end_period - period)
        # Round to integer and ensure at least 1
        current_period = max(1, round(current_period))
        t += current_period

    return timesteps


def once(timestep: int) -> list[int]:
    """Generate a single timestep event.

    Args:
        timestep: The timestep to fire

    Returns:
        List containing single timestep
    """
    return [timestep]


class EventConfig(Handler):
    """Configuration for a timestep-based event.

    Extends Handler with event-specific fields. Inherits filters and mutations from Handler.

    Events fire at specified timesteps, applying mutations to all objects
    that pass the filters. Each event automatically logs a stat when it fires.

    Attributes:
        name: Unique name for this event (used in stat logging as event.<name>)
        target_tag: Tag used to find candidate target objects via TagIndex for efficient lookup
        timesteps: List of timesteps when this event fires
        filters: (inherited) List of filters to select target objects (all must pass)
        mutations: (inherited) List of mutations to apply to matching objects
        max_targets: Maximum number of targets to apply mutations to (0 = unlimited, default 1)

    Note:
        Filters target GridObjects, not agents. Use TagFilter to select
        by tag (name:value), or NearFilter (via isNear helper) to select objects near those matching inner filters.
    """

    name: str = Field(description="Unique name for this event")
    target_tag: str = Field(
        description="Tag used to find candidate target objects via TagIndex for efficient lookup",
    )
    timesteps: list[int] = Field(
        default_factory=list,
        description="List of timesteps when this event fires",
    )
    max_targets: int = Field(
        default=1,
        ge=0,
        description="Maximum number of targets to apply mutations to (0 = unlimited)",
    )
    fallback: Optional[str] = Field(
        default=None,
        description="Event name to fire if no targets match (optional)",
    )
