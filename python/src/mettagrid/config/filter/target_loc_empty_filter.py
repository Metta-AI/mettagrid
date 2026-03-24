"""TargetLocEmpty filter configuration - marker filter for move handlers."""

from __future__ import annotations

from typing import Literal

from mettagrid.base_config import Config


class TargetLocEmptyFilter(Config):
    """Filter that passes when the target cell is empty (no object)."""

    filter_type: Literal["target_loc_empty"] = "target_loc_empty"
