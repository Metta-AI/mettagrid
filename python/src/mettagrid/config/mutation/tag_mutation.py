"""Tag mutation configurations and helper functions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.mutation.mutation import AlignmentEntityTarget, Mutation
from mettagrid.config.tag import Tag


class AddTagMutation(Mutation):
    """Add a tag to an entity.

    This mutation adds a tag to the entity and updates the TagIndex for efficient
    tag-based queries.

    Example:
        AddTagMutation(tag="infected", target=AlignmentEntityTarget.TARGET)
    """

    mutation_type: Literal["add_tag"] = "add_tag"
    target: AlignmentEntityTarget = Field(
        default=AlignmentEntityTarget.TARGET,
        description="Entity to add tag to (actor or target)",
    )
    tag: Tag = Field(description="Tag name to add")


class RemoveTagMutation(Mutation):
    """Remove a tag from an entity.

    This mutation removes a tag from the entity and updates the TagIndex for efficient
    tag-based queries.

    Example:
        RemoveTagMutation(tag="infected", target=AlignmentEntityTarget.TARGET)
    """

    mutation_type: Literal["remove_tag"] = "remove_tag"
    target: AlignmentEntityTarget = Field(
        default=AlignmentEntityTarget.TARGET,
        description="Entity to remove tag from (actor or target)",
    )
    tag: Tag = Field(description="Tag name to remove")


# ===== Helper Mutation Functions =====


def addTag(tag: Tag, target: AlignmentEntityTarget = AlignmentEntityTarget.TARGET) -> AddTagMutation:
    """Mutation: add a tag to an entity.

    This mutation adds a tag to the entity and updates the TagIndex for efficient
    tag-based queries.

    Args:
        tag: Tag name to add.
        target: Entity to add tag to (actor or target). Defaults to TARGET.
    """
    return AddTagMutation(tag=tag, target=target)


def removeTag(tag: Tag, target: AlignmentEntityTarget = AlignmentEntityTarget.TARGET) -> RemoveTagMutation:
    """Mutation: remove a tag from an entity.

    This mutation removes a tag from the entity and updates the TagIndex for efficient
    tag-based queries.

    Args:
        tag: Tag name to remove.
        target: Entity to remove tag from (actor or target). Defaults to TARGET.
    """
    return RemoveTagMutation(tag=tag, target=target)
