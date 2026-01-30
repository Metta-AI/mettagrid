"""Tag type for type-safe tag references in configs."""

from __future__ import annotations

from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class Tag(str):
    """A tag identifier for game objects.

    Use Tag("foo") to create tags. Pydantic fields typed as Tag will
    validate as strings and coerce to Tag instances.

    Examples:
        Tag("infected")
        Tag("type:wall")
        Tag("team:red")
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())


def typeTag(name: str) -> Tag:
    """Return the type tag for an object/agent name.

    Auto-generated type tags use this format. Objects named "wall" get tag "type:wall".

    Args:
        name: The object or agent type name (e.g., "wall", "agent", "assembler")
    """
    return Tag(f"type:{name}")
