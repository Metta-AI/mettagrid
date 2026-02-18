"""Tag type for type-safe tag references in configs."""

from __future__ import annotations

from pydantic import ConfigDict

from mettagrid.base_config import Config


class Tag(Config):
    """A tag identifier for game objects.

    Use tag("foo") to create tags. Pydantic fields typed as Tag will
    validate as strings and coerce to Tag instances.
    """

    model_config = ConfigDict(frozen=True)

    name: str


def tag(name: str) -> Tag:
    return Tag(name=name)


def typeTag(name: str) -> Tag:
    """Return the type tag for an object/agent name.

    Auto-generated type tags use this format. Objects named "wall" get tag "type:wall".

    Args:
        name: The object or agent type name (e.g., "wall", "agent", "hub")
    """
    return Tag(name=f"type:{name}")
