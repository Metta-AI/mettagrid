"""Periodic filter configuration - passes every N timesteps."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from mettagrid.base_config import Config


class PeriodicFilter(Config):
    """Filter that passes at regular timestep intervals.

    Passes when: (timestep - start_on) % period == 0 and timestep >= start_on.
    Does not require a target entity - operates purely on the current timestep.
    """

    filter_type: Literal["periodic"] = "periodic"
    period: int = Field(ge=1, description="Number of timesteps between passes")
    start_on: Optional[int] = Field(
        default=None,
        description="First timestep to pass on. Defaults to period (first fire at tick=period).",
    )
