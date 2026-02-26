"""Game value types for rewards and observations.

GameValue is the base class for values queryable from game state.
Used for rewards (numerators/denominators) and observations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Set, Tuple, Union

from pydantic import Field

from mettagrid.base_config import Config, ConfigStrEnum

if TYPE_CHECKING:
    from mettagrid.config.filter import AnyFilter
    from mettagrid.config.query import AnyQuery


class Scope(ConfigStrEnum):
    """Scope for a game value."""

    AGENT = "agent"
    GAME = "game"


_SCOPE_ALIASES: dict[str, Scope] = {
    "agent": Scope.AGENT,
    "game": Scope.GAME,
}


def _parse_scope(s: str, allowed: Set[Scope], default: Scope = Scope.AGENT) -> Tuple[Scope, str]:
    """Parse an optional 'scope.' prefix from *s*.

    Returns (scope, remainder). If the first dotted segment matches a known
    scope name (or alias), that scope is used; otherwise *default* is returned
    and the full string is the remainder.
    """
    dot = s.find(".")
    if dot != -1:
        prefix = s[:dot].lower()
        if prefix in _SCOPE_ALIASES:
            scope = _SCOPE_ALIASES[prefix]
            if scope not in allowed:
                allowed_str = sorted(sc.value for sc in allowed)
                raise ValueError(f"Scope '{prefix}' is not allowed here (allowed: {allowed_str})")
            return scope, s[dot + 1 :]
    return default, s


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class GameValue(Config):
    """Base class for values queryable from game state."""

    pass


class InventoryValue(GameValue):
    """Inventory item count with explicit scope."""

    item: str
    scope: Scope = Scope.AGENT


class StatValue(GameValue):
    """Stat value with explicit scope."""

    name: str
    scope: Scope = Scope.AGENT
    delta: bool = False


class NumObjectsValue(GameValue):
    """Count of objects by type."""

    object_type: str


class ConstValue(GameValue):
    """A constant numeric value."""

    value: float


class QueryInventoryValue(GameValue):
    """Sum of a resource across objects matched by a query."""

    query: "AnyQuery" = Field(description="Query to find objects whose inventory to sum")
    item: str = Field(description="Resource name to sum")


class QueryCountValue(GameValue):
    """Count of objects matched by a query."""

    query: "AnyQuery" = Field(description="Query to find objects to count")


# ---------------------------------------------------------------------------
# Union of all GameValue types
# ---------------------------------------------------------------------------

AnyGameValue = Union[
    InventoryValue,
    StatValue,
    NumObjectsValue,
    ConstValue,
    QueryInventoryValue,
    QueryCountValue,
]


# ---------------------------------------------------------------------------
# String-parsing helper constructors
# ---------------------------------------------------------------------------


def inv(s: str) -> InventoryValue:
    """Parse 'item' or 'scope.item' into InventoryValue."""
    scope, name = _parse_scope(s, allowed={Scope.AGENT})
    return InventoryValue(item=name, scope=scope)


def stat(s: str, delta: bool = False) -> StatValue:
    """Parse 'name' or 'scope.name' into StatValue."""
    scope, name = _parse_scope(s, allowed={Scope.AGENT, Scope.GAME})
    return StatValue(name=name, scope=scope, delta=delta)


def num(
    s: str,
    filters: "AnyFilter | list[AnyFilter] | None" = None,
) -> NumObjectsValue | QueryCountValue:
    """Create an object-count GameValue, optionally filtered by query filters."""
    if filters is None:
        return NumObjectsValue(object_type=s)

    from mettagrid.config.query import query  # noqa: PLC0415
    from mettagrid.config.tag import typeTag  # noqa: PLC0415

    normalized_filters = filters if isinstance(filters, list) else [filters]
    return QueryCountValue(query=query(typeTag(s), normalized_filters))


def tag(s: str) -> QueryCountValue:
    """Create a QueryCountValue that counts objects with a given tag."""
    from mettagrid.config.query import query  # noqa: PLC0415

    return QueryCountValue(query=query(s))
