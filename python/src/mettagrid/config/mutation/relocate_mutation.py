"""Relocate mutation configuration - moves actor to target cell."""

from __future__ import annotations

from typing import Literal

from mettagrid.base_config import Config


class RelocateMutation(Config):
    """Move the actor to the target cell."""

    mutation_type: Literal["relocate"] = "relocate"
