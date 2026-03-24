"""Swap mutation configuration - swaps actor and target positions."""

from __future__ import annotations

from typing import Literal

from mettagrid.base_config import Config


class SwapMutation(Config):
    """Swap the positions of actor and target."""

    mutation_type: Literal["swap"] = "swap"
