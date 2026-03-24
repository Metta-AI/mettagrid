"""SpawnObjectMutation configuration - spawns an object at the target location."""

from __future__ import annotations

from typing import Literal

from mettagrid.base_config import Config


class SpawnObjectMutation(Config):
    """Spawn an object of the given type at the target cell."""

    mutation_type: Literal["spawn_object"] = "spawn_object"
    object_type: str  # Object type name to spawn at target_location
