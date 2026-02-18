"""Tag mutation configurations and helper functions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.mutation.mutation import EntityTarget, Mutation
from mettagrid.config.tag import Tag


class AddTagMutation(Mutation):
    """Add a tag to an entity.

    This mutation adds a tag to the entity and updates the TagIndex for efficient
    tag-based queries.

    Example:
        AddTagMutation(tag="infected", target=EntityTarget.TARGET)
    """

    mutation_type: Literal["add_tag"] = "add_tag"
    target: EntityTarget = Field(
        default=EntityTarget.TARGET,
        description="Entity to add tag to (actor or target)",
    )
    tag: Tag = Field(description="Tag name to add")


class RemoveTagMutation(Mutation):
    """Remove a tag from an entity.

    This mutation removes a tag from the entity and updates the TagIndex for efficient
    tag-based queries.

    Example:
        RemoveTagMutation(tag="infected", target=EntityTarget.TARGET)
    """

    mutation_type: Literal["remove_tag"] = "remove_tag"
    target: EntityTarget = Field(
        default=EntityTarget.TARGET,
        description="Entity to remove tag from (actor or target)",
    )
    tag: Tag = Field(description="Tag name to remove")


class RemoveTagsWithPrefixMutation(Mutation):
    """Remove all tags that start with a prefix from an entity.

    This expands to one RemoveTagMutation per matching tag during Python->C++
    conversion.
    """

    mutation_type: Literal["remove_tags_with_prefix"] = "remove_tags_with_prefix"
    target: EntityTarget = Field(
        default=EntityTarget.TARGET,
        description="Entity to remove matching tags from (actor or target)",
    )
    prefix: str = Field(description="Tag prefix to remove (e.g. 'team:')")


# ===== Helper Mutation Functions =====


def addTag(tag: str | Tag, target: EntityTarget = EntityTarget.TARGET) -> AddTagMutation:
    """Mutation: add a tag to an entity.

    Args:
        tag: Tag name to add (str or Tag).
        target: Entity to add tag to (actor or target). Defaults to TARGET.
    """
    return AddTagMutation(tag=Tag(name=tag) if isinstance(tag, str) else tag, target=target)


def removeTag(tag: str | Tag, target: EntityTarget = EntityTarget.TARGET) -> RemoveTagMutation:
    """Mutation: remove a tag from an entity.

    Args:
        tag: Tag name to remove (str or Tag).
        target: Entity to remove tag from (actor or target). Defaults to TARGET.
    """
    return RemoveTagMutation(tag=Tag(name=tag) if isinstance(tag, str) else tag, target=target)


def RemoveTagsWithPrefix(
    prefix: str,
    target: EntityTarget = EntityTarget.TARGET,
) -> RemoveTagsWithPrefixMutation:
    """Mutation: remove all tags from entity that match a prefix."""
    return RemoveTagsWithPrefixMutation(prefix=prefix, target=target)


def removeTagPrefix(
    prefix: str,
    target: EntityTarget = EntityTarget.TARGET,
) -> RemoveTagsWithPrefixMutation:
    """Mutation helper alias: remove all tags from entity that match a prefix."""
    return RemoveTagsWithPrefix(prefix=prefix, target=target)
