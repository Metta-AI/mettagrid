"""Base mutation configuration and common types."""

from __future__ import annotations

from enum import StrEnum, auto

from mettagrid.base_config import Config


class EntityTarget(StrEnum):
    """Target entity for mutation operations."""

    ACTOR = auto()
    TARGET = auto()
    ACTOR_COLLECTIVE = auto()
    TARGET_COLLECTIVE = auto()


class AlignmentEntityTarget(StrEnum):
    """Target entity for alignment/freeze operations (subset of EntityTarget)."""

    ACTOR = auto()
    TARGET = auto()


class Mutation(Config):
    """Base class for handler mutations."""

    pass


# AnyMutation is defined in mutation/__init__.py where all concrete types are real imports.
