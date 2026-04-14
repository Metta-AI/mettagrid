"""Push-object mutation configuration - shoves the target cell one step further."""

from __future__ import annotations

from typing import Literal

from mettagrid.base_config import Config


class PushObjectMutation(Config):
    """Push ``ctx.target`` one cell further along the actor->target direction.

    The direction vector ``target - actor`` is clamped independently on
    each axis to ``[-1, 1]``, so cardinal adjacency pushes by 1 cell in
    that direction, diagonal adjacency pushes diagonally by 1, and
    farther actor/target separations still yield a unit step (never a
    proportional push).

    Sets ``ctx.mutation_failed = True`` if the destination is off-grid
    or occupied by another object.
    """

    mutation_type: Literal["push_object"] = "push_object"
