"""SetRelativeTarget mutation - set ctx.target_location to an actor-relative cell."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.base_config import Config

Direction = Literal[
    "north",
    "south",
    "east",
    "west",
    "northeast",
    "northwest",
    "southeast",
    "southwest",
]


class SetRelativeTargetMutation(Config):
    """Set ``ctx.target_location`` to a cell relative to the actor.

    Computes ``actor.location + direction * distance`` and writes the
    result to ``ctx.target_location``. Also sets ``ctx.target`` to the
    object occupying that cell (or ``None`` if the cell is empty) and
    updates ``ctx.move_direction`` to the chosen orientation so that
    downstream mutations such as ``RelocateMutation`` or
    ``PushObjectMutation`` behave as if the move action had picked this
    direction.

    Sets ``ctx.mutation_failed = True`` if the resulting cell is
    off-grid or the actor is missing.

    Example — event that moves matching agents one cell north::

        EventConfig(
            name="push_agents_north",
            target_query=query(typeTag("agent")),
            timesteps=[50, 100, 150],
            mutations=[
                SetRelativeTargetMutation(direction="north"),
                RelocateMutation(),
            ],
        )
    """

    mutation_type: Literal["set_relative_target"] = "set_relative_target"
    direction: Direction = Field(description="Cardinal or diagonal direction from the actor.")
    distance: int = Field(default=1, ge=1, description="Number of cells along ``direction``.")
