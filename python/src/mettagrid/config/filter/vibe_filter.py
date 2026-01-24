"""Vibe filter configuration and helper functions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.filter.filter import Filter, HandlerTarget


class VibeFilter(Filter):
    """Filter that checks if the target entity has a specific vibe."""

    filter_type: Literal["vibe"] = "vibe"
    vibe: str = Field(description="Vibe name that must match")


# ===== Helper Filter Functions =====


def actorVibe(vibe: str) -> VibeFilter:
    """Filter: actor must have the specified vibe."""
    return VibeFilter(target=HandlerTarget.ACTOR, vibe=vibe)


def targetVibe(vibe: str) -> VibeFilter:
    """Filter: target must have the specified vibe."""
    return VibeFilter(target=HandlerTarget.TARGET, vibe=vibe)
