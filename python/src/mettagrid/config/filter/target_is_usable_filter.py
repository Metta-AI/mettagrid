"""TargetIsUsable filter configuration - marker filter for move handlers."""

from __future__ import annotations

from typing import Literal

from mettagrid.base_config import Config


class TargetIsUsableFilter(Config):
    """Filter that passes when the target implements the Usable interface."""

    filter_type: Literal["target_is_usable"] = "target_is_usable"
