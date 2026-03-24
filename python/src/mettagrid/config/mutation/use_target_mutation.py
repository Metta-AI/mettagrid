"""UseTarget mutation configuration - delegates to target's onUse handler."""

from __future__ import annotations

from typing import Literal

from mettagrid.base_config import Config


class UseTargetMutation(Config):
    """Delegate to the target object's onUse handler chain."""

    mutation_type: Literal["use_target"] = "use_target"


def useTarget() -> UseTargetMutation:
    """Create a UseTargetMutation."""
    return UseTargetMutation()
