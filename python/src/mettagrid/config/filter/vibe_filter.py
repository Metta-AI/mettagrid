"""Vibe filter configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.filter.filter import Filter, HandlerTarget


class VibeFilter(Filter):
    """Filter that checks if the target entity has a specific vibe."""

    filter_type: Literal["vibe"] = "vibe"
    vibe: str = Field(description="Vibe name that must match")


# ===== Helper Filter Functions =====


def targetVibe(vibe: str) -> VibeFilter:
    """Filter: target has the specified vibe.

    Args:
        vibe: The vibe name to check for (e.g., "charger", "up", "down")
    """
    return VibeFilter(target=HandlerTarget.TARGET, vibe=vibe)


def actorVibe(vibe: str) -> VibeFilter:
    """Filter: actor has the specified vibe.

    Args:
        vibe: The vibe name to check for (e.g., "charger", "up", "down")
    """
    return VibeFilter(target=HandlerTarget.ACTOR, vibe=vibe)
