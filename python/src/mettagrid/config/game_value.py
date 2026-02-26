"""Game value types for rewards and observations.

GameValue is the base class for values queryable from game state.
Used for rewards (numerators/denominators) and observations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Set, Tuple, Union

from pydantic import Field, model_validator

from mettagrid.base_config import Config, ConfigStrEnum
from mettagrid.config.query import AnyQuery

if TYPE_CHECKING:
    from mettagrid.config.filter.filter import Filter


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


class ConstValue(GameValue):
    """A constant numeric value."""

    value: float


def val(x: int | float) -> ConstValue:
    """Create a ConstValue from a numeric literal."""
    return ConstValue(value=float(x))


class QueryInventoryValue(GameValue):
    """Sum of a resource across objects matched by a query."""

    query: AnyQuery = Field(description="Query to find objects whose inventory to sum")
    item: str = Field(description="Resource name to sum")


class QueryCountValue(GameValue):
    """Count of objects matched by a query."""

    query: AnyQuery = Field(description="Query to find objects to count")


# Backwards-friendly canonical naming.
CountQueryValue = QueryCountValue


class SumGameValue(GameValue):
    """Sum a list of game values."""

    values: list["AnyGameValue"] = Field(min_length=1)
    weights: list[float] | None = None
    log: bool = False

    @model_validator(mode="after")
    def _validate_weights(self) -> "SumGameValue":
        if self.weights is not None and len(self.weights) != len(self.values):
            raise ValueError("SumGameValue.weights must have same length as values")
        return self


class RatioGameValue(GameValue):
    """Ratio of two game values."""

    numerator: "AnyGameValue"
    denominator: "AnyGameValue"


class MaxGameValue(GameValue):
    """Maximum value from a list of game values."""

    values: list["AnyGameValue"] = Field(min_length=1)


class MinGameValue(GameValue):
    """Minimum value from a list of game values."""

    values: list["AnyGameValue"] = Field(min_length=1)


AnyGameValue = Union[
    InventoryValue,
    StatValue,
    ConstValue,
    QueryInventoryValue,
    QueryCountValue,
    SumGameValue,
    RatioGameValue,
    MaxGameValue,
    MinGameValue,
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
    filters: "Filter | list[Filter] | None" = None,
) -> QueryCountValue:
    """Create a count GameValue from a tag query source, optionally filtered."""
    from mettagrid.config.query import query  # noqa: PLC0415

    normalized_filters = filters if isinstance(filters, list) else [filters] if filters is not None else []
    return QueryCountValue(query=query(s, normalized_filters))  # pyright: ignore[reportArgumentType]


def num_tagged(s: str) -> QueryCountValue:
    """Create a QueryCountValue that counts objects with a given tag."""
    from mettagrid.config.query import query  # noqa: PLC0415

    return QueryCountValue(query=query(s))


def tag(s: str) -> QueryCountValue:
    """Create a QueryCountValue that counts objects with a given tag."""
    return num_tagged(s)


def weighted_sum(
    weighted_values: list[tuple[float, AnyGameValue]],
    *,
    log: bool = False,
    min: int | float | None = None,
    max: int | float | None = None,
) -> AnyGameValue:
    """Create a weighted sum from ``[(weight, game_value), ...]``, optionally clamped."""
    values = [value for _, value in weighted_values]
    weights = [weight for weight, _ in weighted_values]
    summed_value: AnyGameValue = SumGameValue(values=values, weights=weights, log=log)
    if min is not None:
        summed_value = max_value([summed_value, val(min)])
    if max is not None:
        summed_value = min_value([summed_value, val(max)])
    return summed_value


def GameValueRatio(num_gv: AnyGameValue, denom_gv: AnyGameValue) -> RatioGameValue:
    """Create a ratio game value with safe denominator handling in C++ runtime."""
    return RatioGameValue(numerator=num_gv, denominator=denom_gv)


def max_value(values: list[AnyGameValue]) -> MaxGameValue:
    """Create a max combinator game value."""
    return MaxGameValue(values=values)


def min_value(values: list[AnyGameValue]) -> MinGameValue:
    """Create a min combinator game value."""
    return MinGameValue(values=values)


# Rebuild recursive combinator schemas after all concrete variants are defined.
_rebuild_ns = {
    "AnyFilter": Any,
    "AnyQuery": AnyQuery,
    "AnyGameValue": AnyGameValue,
    "SumGameValue": SumGameValue,
    "RatioGameValue": RatioGameValue,
    "MaxGameValue": MaxGameValue,
    "MinGameValue": MinGameValue,
}
SumGameValue.model_rebuild(_types_namespace=_rebuild_ns)
RatioGameValue.model_rebuild(_types_namespace=_rebuild_ns)
MaxGameValue.model_rebuild(_types_namespace=_rebuild_ns)
MinGameValue.model_rebuild(_types_namespace=_rebuild_ns)
