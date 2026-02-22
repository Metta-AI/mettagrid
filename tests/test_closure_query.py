"""Tests for ClosureQuery Python config model and C++ integration.

Unit tests verify construction, serialization, discriminated union (AnyQuery),
use inside MaxDistanceFilter / QueryInventoryMutation, and nested queries.
"""

from mettagrid.config.filter import (
    ClosureQuery,
    HandlerTarget,
    MaxDistanceFilter,
    Query,
    hasTag,
    isA,
    isNear,
    maxDistance,
    query,
)
from mettagrid.config.mutation import (
    QueryInventoryMutation,
    queryDeposit,
)
from mettagrid.config.tag import typeTag


class TestClosureQueryConstruction:
    """Test ClosureQuery model construction."""

    def test_basic_construction(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(1)],
        )
        assert cq.query_type == "closure"
        assert cq.source == typeTag("hub")
        assert len(cq.edge_filters) == 1

    def test_with_result_filters(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(1)],
            filters=[isA("junction")],
        )
        assert len(cq.filters) == 1
        assert len(cq.edge_filters) == 1

    def test_multiple_edge_filters(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(2), hasTag("team:red")],
        )
        assert len(cq.edge_filters) == 2

    def test_source_with_filters(self):
        cq = ClosureQuery(
            source=query(typeTag("hub"), [hasTag("team:red")]),
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(1)],
        )
        assert isinstance(cq.source, Query)
        assert len(cq.source.filters) == 1

    def test_max_items(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(1)],
            max_items=10,
        )
        assert cq.max_items == 10

    def test_order_by_random(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(1)],
            order_by="random",
        )
        assert cq.order_by == "random"


class TestMaxDistanceModes:
    """Test MaxDistanceFilter binary vs unary modes."""

    def test_binary_mode(self):
        f = maxDistance(10)
        assert f.filter_type == "max_distance"
        assert f.query is None
        assert f.radius == 10

    def test_unary_mode(self):
        f = isNear(typeTag("junction"), radius=3)
        assert f.filter_type == "max_distance"
        assert f.query is not None
        assert f.radius == 3


class TestQueryDiscriminator:
    """Test AnyQuery discriminated union."""

    def test_query_type_tag(self):
        q = query(typeTag("hub"))
        assert q.query_type == "query"

    def test_closure_type_tag(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(1)],
        )
        assert cq.query_type == "closure"

    def test_query_max_items(self):
        q = Query(source=typeTag("hub"), max_items=5)
        assert q.max_items == 5

    def test_query_order_by(self):
        q = Query(source=typeTag("hub"), order_by="random")
        assert q.order_by == "random"


class TestClosureQuerySerialization:
    """Test ClosureQuery serialization/deserialization round-trip."""

    def test_round_trip(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(3)],
        )
        data = cq.model_dump()
        assert data["query_type"] == "closure"
        assert data["source"] == typeTag("hub")
        assert len(data["edge_filters"]) == 1
        assert data["edge_filters"][0]["filter_type"] == "max_distance"
        assert data["edge_filters"][0]["radius"] == 3
        assert data["edge_filters"][0]["query"] is None

    def test_deserialize(self):
        data = {
            "query_type": "closure",
            "source": typeTag("hub"),
            "candidates": {"query_type": "query", "source": typeTag("wire"), "filters": []},
            "edge_filters": [
                {
                    "filter_type": "max_distance",
                    "target": "target",
                    "query": None,
                    "radius": 2,
                }
            ],
            "filters": [],
        }
        cq = ClosureQuery.model_validate(data)
        assert cq.query_type == "closure"
        assert cq.source == typeTag("hub")
        assert len(cq.edge_filters) == 1
        assert isinstance(cq.edge_filters[0], MaxDistanceFilter)
        assert cq.edge_filters[0].radius == 2
        assert cq.edge_filters[0].query is None

    def test_query_serialization(self):
        q = Query(source=typeTag("hub"), max_items=5, order_by="random")
        data = q.model_dump()
        assert data["query_type"] == "query"
        assert data["source"] == typeTag("hub")
        assert data["max_items"] == 5
        assert data["order_by"] == "random"


class TestClosureInFilters:
    """Test ClosureQuery used inside filters."""

    def test_closure_in_max_distance_filter(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(2)],
        )
        f = MaxDistanceFilter(
            target=HandlerTarget.TARGET,
            query=cq,
            radius=3,
        )
        assert f.filter_type == "max_distance"
        assert f.query.query_type == "closure"
        assert f.radius == 3

    def test_closure_via_is_near_helper(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(1)],
        )
        f = isNear(cq, radius=5)
        assert f.filter_type == "max_distance"
        assert f.query.query_type == "closure"
        assert f.radius == 5


class TestClosureInMutations:
    """Test ClosureQuery used inside mutations."""

    def test_closure_in_query_inventory_mutation(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(1)],
        )
        m = QueryInventoryMutation(
            query=cq,
            deltas={"energy": 10},
        )
        assert m.mutation_type == "query_inventory"
        assert m.query.query_type == "closure"

    def test_closure_with_query_deposit_helper(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(1)],
        )
        m = queryDeposit(cq, {"energy": 5})
        assert m.query.query_type == "closure"
        assert m.deltas == {"energy": 5}


class TestNestedClosureQuery:
    """Test ClosureQuery with nested source queries."""

    def test_nested_closure_source(self):
        """A ClosureQuery whose source is itself a ClosureQuery."""
        inner = ClosureQuery(
            source=typeTag("power_plant"),
            candidates=query(typeTag("power_line")),
            edge_filters=[maxDistance(1)],
        )
        outer = ClosureQuery(
            source=inner,
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(2)],
        )
        assert outer.query_type == "closure"
        assert isinstance(outer.source, ClosureQuery)
        assert outer.source.query_type == "closure"
        assert outer.source.source == typeTag("power_plant")

    def test_nested_serialization_round_trip(self):
        inner = ClosureQuery(
            source=typeTag("core"),
            candidates=query(typeTag("conduit")),
            edge_filters=[maxDistance(1)],
        )
        outer = ClosureQuery(
            source=inner,
            candidates=query(typeTag("wire")),
            edge_filters=[maxDistance(1)],
            filters=[isA("junction")],
        )
        data = outer.model_dump()
        restored = ClosureQuery.model_validate(data)
        assert isinstance(restored.source, ClosureQuery)
        assert restored.source.query_type == "closure"
        assert restored.source.source == typeTag("core")
        assert len(restored.filters) == 1
