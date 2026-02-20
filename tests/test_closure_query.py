"""Tests for ClosureQuery Python config model and C++ integration.

Unit tests verify construction, serialization, discriminated union (AnyQuery),
use inside MaxDistanceFilter / QueryInventoryMutation, and nested queries.

Integration tests exercise the full Python config -> C++ conversion -> simulation
pipeline using ClosureQuery with edge_filters (maxDistance) and mutations.
"""

from mettagrid.config.event_config import EventConfig
from mettagrid.config.filter import (
    ClosureQuery,
    HandlerTarget,
    MaterializedQuery,
    MaxDistanceFilter,
    Query,
    hasTag,
    isA,
    isNear,
    maxDistance,
    query,
)
from mettagrid.config.handler_config import Handler
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    CollectiveConfig,
    GameConfig,
    GridObjectConfig,
    MettaGridConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.config.mutation import (
    QueryInventoryMutation,
    addTag,
    alignTo,
    queryDeposit,
    recomputeMaterializedQuery,
    removeTag,
)
from mettagrid.config.tag import typeTag
from mettagrid.map_builder.ascii import AsciiMapBuilder
from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
from mettagrid.simulator import Simulation


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


# ===========================================================================
# Integration tests: ClosureQuery through the full C++ simulation pipeline
# ===========================================================================


def _count_by_collective(sim: Simulation, object_type: str) -> dict[int, int]:
    """Count objects of given type by collective_id (-1 = unaligned)."""
    objects = sim.grid_objects()
    counts: dict[int, int] = {}
    for obj in objects.values():
        if obj.get("type_name") == object_type:
            cid = obj.get("collective_id", -1)
            counts[cid] = counts.get(cid, 0) + 1
    return counts


def _get_collective_id(sim: Simulation, name: str) -> int:
    for obj in sim.grid_objects().values():
        if obj.get("collective_name") == name:
            return obj.get("collective_id", -1)
    return -1


class TestClosureQueryIntegration:
    """Integration tests: ClosureQuery through the full C++ pipeline.

    These tests use events with isNear(ClosureQuery(...)) to verify that
    the BFS-based closure query finds the right set of objects, and that
    only targets near those objects are affected.
    """

    def test_event_near_connected_network_aligns_junction(self):
        """Junction adjacent to a hub->wire chain gets aligned via ClosureQuery.

        Map layout (7x7):
            # # # # # # #
            # . . . . . #
            # . H W J . #   H=hub, W=wire, J=junction
            # . . . . . #
            # . . @ . . #   @=agent
            # # # # # # #
        """
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=7, height=7, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                agent=AgentConfig(collective="team_a"),
                objects={
                    "wall": WallConfig(tags=[typeTag("wall")]),
                    "hub": GridObjectConfig(name="hub", map_name="hub", tags=[typeTag("hub")]),
                    "wire": GridObjectConfig(name="wire", map_name="wire", tags=[typeTag("wire")]),
                    "junction": WallConfig(name="junction", tags=[typeTag("junction")]),
                },
                collectives={
                    "team_a": CollectiveConfig(),
                    "team_b": CollectiveConfig(),
                },
                events={
                    "connect_junctions": EventConfig(
                        name="connect_junctions",
                        target_query=query(typeTag("junction")),
                        timesteps=[3],
                        filters=[
                            isA("junction"),
                            isNear(
                                ClosureQuery(
                                    source=typeTag("hub"),
                                    candidates=query(typeTag("wire")),
                                    edge_filters=[maxDistance(1)],
                                ),
                                radius=1,
                            ),
                        ],
                        mutations=[alignTo("team_b")],
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#", "#", "#"],
                        ["#", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", "H", "W", "J", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", "@", ".", ".", "#"],
                        ["#", "#", "#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name={**DEFAULT_CHAR_TO_NAME, "H": "hub", "W": "wire", "J": "junction"},
                ),
            ),
        )

        sim = Simulation(config)

        before = _count_by_collective(sim, "junction")
        assert before.get(-1, 0) == 1, "Junction should start unaligned"

        for _ in range(4):
            sim.step()

        team_b_id = _get_collective_id(sim, "team_b")
        after = _count_by_collective(sim, "junction")
        assert after.get(team_b_id, 0) == 1, "Junction near connected network should be aligned"

    def test_disconnected_junction_not_affected(self):
        """Junction far from the hub->wire network is NOT affected by the event.

        Map layout (9x7):
            # # # # # # # # #
            # . . . . . . . #
            # . H W J . . D #   D=disconnected junction
            # . . . . . . . #
            # . . . @ . . . #
            # # # # # # # # #
        """
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=9, height=9, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                agent=AgentConfig(collective="team_a"),
                objects={
                    "wall": WallConfig(tags=[typeTag("wall")]),
                    "hub": GridObjectConfig(name="hub", map_name="hub", tags=[typeTag("hub")]),
                    "wire": GridObjectConfig(name="wire", map_name="wire", tags=[typeTag("wire")]),
                    "junction": WallConfig(name="junction", tags=[typeTag("junction")]),
                },
                collectives={
                    "team_a": CollectiveConfig(),
                    "team_b": CollectiveConfig(),
                },
                events={
                    "connect_junctions": EventConfig(
                        name="connect_junctions",
                        target_query=query(typeTag("junction")),
                        timesteps=[3],
                        filters=[
                            isA("junction"),
                            isNear(
                                ClosureQuery(
                                    source=typeTag("hub"),
                                    candidates=query(typeTag("wire")),
                                    edge_filters=[maxDistance(1)],
                                ),
                                radius=1,
                            ),
                        ],
                        mutations=[alignTo("team_b")],
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", "H", "W", "J", ".", ".", "D", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", "@", ".", ".", ".", "#"],
                        ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name={
                        **DEFAULT_CHAR_TO_NAME,
                        "H": "hub",
                        "W": "wire",
                        "J": "junction",
                        "D": "junction",
                    },
                ),
            ),
        )

        sim = Simulation(config)

        before = _count_by_collective(sim, "junction")
        assert before.get(-1, 0) == 2, "Both junctions should start unaligned"

        for _ in range(4):
            sim.step()

        team_b_id = _get_collective_id(sim, "team_b")
        after = _count_by_collective(sim, "junction")
        assert after.get(team_b_id, 0) == 1, "Only 1 junction (near network) should be aligned"
        assert after.get(-1, 0) == 1, "Disconnected junction should remain unaligned"

    def test_closure_edge_radius_2_bridges_gap(self):
        """maxDistance(2) in edge_filters lets BFS bridge a gap between hub and wire.

        Map layout (9x7):
            # # # # # # # # #
            # . . . . . . . #
            # . H . W J . . #   Gap of 1 between hub(2,2) and wire(2,4)
            # . . . . . . . #
            # . . . . @ . . #
            # # # # # # # # #

        With maxDistance(1), wire is NOT reachable (L2 distance 2).
        With maxDistance(2), wire IS reachable.
        """

        def _make_config(edge_radius):
            return MettaGridConfig(
                game=GameConfig(
                    num_agents=1,
                    obs=ObsConfig(width=9, height=9, num_tokens=100),
                    max_steps=100,
                    actions=ActionsConfig(noop=NoopActionConfig()),
                    resource_names=[],
                    agent=AgentConfig(collective="team_a"),
                    objects={
                        "wall": WallConfig(tags=[typeTag("wall")]),
                        "hub": GridObjectConfig(name="hub", map_name="hub", tags=[typeTag("hub")]),
                        "wire": GridObjectConfig(name="wire", map_name="wire", tags=[typeTag("wire")]),
                        "junction": WallConfig(name="junction", tags=[typeTag("junction")]),
                    },
                    collectives={
                        "team_a": CollectiveConfig(),
                        "team_b": CollectiveConfig(),
                    },
                    events={
                        "connect_junctions": EventConfig(
                            name="connect_junctions",
                            target_query=query(typeTag("junction")),
                            timesteps=[3],
                            filters=[
                                isA("junction"),
                                isNear(
                                    ClosureQuery(
                                        source=typeTag("hub"),
                                        candidates=query(typeTag("wire")),
                                        edge_filters=[maxDistance(edge_radius)],
                                    ),
                                    radius=1,
                                ),
                            ],
                            mutations=[alignTo("team_b")],
                        ),
                    },
                    map_builder=AsciiMapBuilder.Config(
                        map_data=[
                            ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
                            ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                            ["#", ".", "H", ".", "W", "J", ".", ".", "#"],
                            ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                            ["#", ".", ".", ".", ".", "@", ".", ".", "#"],
                            ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
                        ],
                        char_to_map_name={**DEFAULT_CHAR_TO_NAME, "H": "hub", "W": "wire", "J": "junction"},
                    ),
                ),
            )

        # radius=1: wire unreachable from hub (distance 2), junction NOT aligned
        sim1 = Simulation(_make_config(edge_radius=1))
        for _ in range(4):
            sim1.step()
        after1 = _count_by_collective(sim1, "junction")
        assert after1.get(-1, 0) == 1, "With radius=1, junction should stay unaligned (wire not reachable)"

        # radius=2: wire reachable from hub, junction gets aligned
        sim2 = Simulation(_make_config(edge_radius=2))
        for _ in range(4):
            sim2.step()
        team_b_id = _get_collective_id(sim2, "team_b")
        after2 = _count_by_collective(sim2, "junction")
        assert after2.get(team_b_id, 0) == 1, "With radius=2, junction should be aligned (wire reachable)"

    def test_closure_chain_propagation(self):
        """Closure BFS propagates through a chain of wires via multi-hop.

        Map layout (11x7):
            # # # # # # # # # # #
            # . . . . . . . . . #
            # . H W W W W W J . #   Chain: hub -> 5 wires -> junction adjacent
            # . . . . . . . . . #
            # . . . . . @ . . . #
            # # # # # # # # # # #

        maxDistance(1) in edge_filters means BFS chains through adjacent wires.
        """
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=11, height=11, num_tokens=200),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                agent=AgentConfig(collective="team_a"),
                objects={
                    "wall": WallConfig(tags=[typeTag("wall")]),
                    "hub": GridObjectConfig(name="hub", map_name="hub", tags=[typeTag("hub")]),
                    "wire": GridObjectConfig(name="wire", map_name="wire", tags=[typeTag("wire")]),
                    "junction": WallConfig(name="junction", tags=[typeTag("junction")]),
                },
                collectives={
                    "team_a": CollectiveConfig(),
                    "team_b": CollectiveConfig(),
                },
                events={
                    "connect_junctions": EventConfig(
                        name="connect_junctions",
                        target_query=query(typeTag("junction")),
                        timesteps=[3],
                        filters=[
                            isA("junction"),
                            isNear(
                                ClosureQuery(
                                    source=typeTag("hub"),
                                    candidates=query(typeTag("wire")),
                                    edge_filters=[maxDistance(1)],
                                ),
                                radius=1,
                            ),
                        ],
                        mutations=[alignTo("team_b")],
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", "H", "W", "W", "W", "W", "W", "J", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", "@", ".", ".", ".", "#"],
                        ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name={**DEFAULT_CHAR_TO_NAME, "H": "hub", "W": "wire", "J": "junction"},
                ),
            ),
        )

        sim = Simulation(config)
        for _ in range(4):
            sim.step()

        team_b_id = _get_collective_id(sim, "team_b")
        after = _count_by_collective(sim, "junction")
        assert after.get(team_b_id, 0) == 1, "Junction at end of wire chain should be aligned"


# ===========================================================================
# Multi-hop closure test with on/off junctions
# ===========================================================================


def _make_tag_checker_from_sim(sim, cfg):
    """Return a helper that checks if an object at (r, c) has a given tag."""
    id_map = cfg.game.id_map()
    tag_names = id_map.tag_names()
    tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}

    def has_tag(tag_name, row, col):
        objects = sim._c_sim.grid_objects()
        for _obj_id, obj_data in objects.items():
            if obj_data["r"] == row and obj_data["c"] == col:
                return obj_data["has_tag"](tag_name_to_id[tag_name])
        return False

    return has_tag


class TestMultiHopClosure:
    """Comprehensive multi-hop closure tests with maxDistance in edge_filters.

    Verifies that the BFS uses edge_filters with (net_member, candidate) context
    to produce correct multi-hop transitive closure.

    Map layout (32 wide, 8 tall):
        Row 0: walls
        Row 1: empty
        Row 2: . H . . . A . . . . B . . . . . C . . . . . . . . . D . . . .
        Row 3: . . . X . . . . . . . . . . . . . . . . . . . . . . . . . . .
        Row 4: . . . . . . . . Y . . . . . . . . . . . . . . . . . . . . . .
        Row 5: empty
        Row 6: . . . . . . . . . . . . . . . . . @ . . . . . . . . . . . . .
        Row 7: walls

    H = hub (source) at (2,1)
    A = "on" junction at (2,5)  — distance 4 from H -> 1 hop, INCLUDED
    B = "on" junction at (2,10) — distance 5 from A -> 2 hops, INCLUDED
    C = "on" junction at (2,16) — distance 6 from B -> 3 hops, NOT included (>5)
    D = "on" junction at (2,26) — distance 10 from C -> isolated, NOT included
    X = "off" junction at (3,3)  — near hub, wrong tag -> NOT included
    Y = "off" junction at (4,8)  — near A, wrong tag -> NOT included
    """

    @staticmethod
    def _build_map(width=32, height=8):
        """Build the map_data grid with specific object placements."""
        grid = []
        for r in range(height):
            if r == 0 or r == height - 1:
                grid.append(["#"] * width)
            else:
                grid.append(["#"] + ["."] * (width - 2) + ["#"])

        grid[2][1] = "H"  # hub
        grid[2][5] = "A"  # on_junction A (dist 4 from H)
        grid[2][10] = "B"  # on_junction B (dist 5 from A)
        grid[2][16] = "C"  # on_junction C (dist 6 from B)
        grid[2][26] = "D"  # on_junction D (dist 10 from C)
        grid[3][3] = "X"  # off_junction X (near hub)
        grid[4][8] = "Y"  # off_junction Y (near A)
        grid[6][17] = "@"  # agent
        return grid

    def _make_multi_hop_config(self, hop_radius=5):
        return MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=11, height=11, num_tokens=200),
                max_steps=10,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                agent=AgentConfig(collective="team_a"),
                objects={
                    "wall": WallConfig(tags=[typeTag("wall")]),
                    "hub": GridObjectConfig(name="hub", map_name="hub", tags=[typeTag("hub")]),
                    "on_junction": GridObjectConfig(
                        name="on_junction", map_name="on_junction", tags=[typeTag("junction"), "on"]
                    ),
                    "off_junction": GridObjectConfig(
                        name="off_junction", map_name="off_junction", tags=[typeTag("junction"), "off"]
                    ),
                },
                tags=["on", "off"],
                collectives={
                    "team_a": CollectiveConfig(),
                },
                materialize_queries=[
                    MaterializedQuery(
                        tag="network",
                        query=ClosureQuery(
                            source=typeTag("hub"),
                            candidates=query(typeTag("junction"), [hasTag("on")]),
                            edge_filters=[maxDistance(hop_radius)],
                        ),
                    ),
                ],
                map_builder=AsciiMapBuilder.Config(
                    map_data=self._build_map(),
                    char_to_map_name={
                        **DEFAULT_CHAR_TO_NAME,
                        "H": "hub",
                        "A": "on_junction",
                        "B": "on_junction",
                        "C": "on_junction",
                        "D": "on_junction",
                        "X": "off_junction",
                        "Y": "off_junction",
                    },
                ),
            ),
        )

    def test_multi_hop_chain_included(self):
        """On-junctions reachable through chain within hop radius are included."""
        cfg = self._make_multi_hop_config(hop_radius=5)
        sim = Simulation(cfg)
        has_tag = _make_tag_checker_from_sim(sim, cfg)

        # Hub is always in closure (it's the source)
        assert has_tag("network", 2, 1), "Hub should be in network"
        # A at dist 4 from hub -> within radius 5 -> 1 hop
        assert has_tag("network", 2, 5), "On-junction A (1 hop, dist 4) should be in network"
        # B at dist 5 from A -> within radius 5 -> 2 hops
        assert has_tag("network", 2, 10), "On-junction B (2 hops, dist 5 from A) should be in network"

    def test_beyond_hop_radius_excluded(self):
        """On-junction beyond hop radius from nearest chain member is excluded."""
        cfg = self._make_multi_hop_config(hop_radius=5)
        sim = Simulation(cfg)
        has_tag = _make_tag_checker_from_sim(sim, cfg)

        # C at dist 6 from B -> exceeds radius 5 -> NOT reachable
        assert not has_tag("network", 2, 16), "On-junction C (dist 6 from B, > radius 5) should NOT be in network"
        # D is even further
        assert not has_tag("network", 2, 26), "On-junction D (isolated) should NOT be in network"

    def test_wrong_tag_excluded(self):
        """Off-junctions near the chain are excluded (don't match candidates query)."""
        cfg = self._make_multi_hop_config(hop_radius=5)
        sim = Simulation(cfg)
        has_tag = _make_tag_checker_from_sim(sim, cfg)

        assert not has_tag("network", 3, 3), "Off-junction X (near hub) should NOT be in network"
        assert not has_tag("network", 4, 8), "Off-junction Y (near A) should NOT be in network"

    def test_larger_radius_includes_more(self):
        """Increasing hop radius brings more junctions into the closure."""
        cfg = self._make_multi_hop_config(hop_radius=6)
        sim = Simulation(cfg)
        has_tag = _make_tag_checker_from_sim(sim, cfg)

        # With radius 6, C at dist 6 from B IS now reachable
        assert has_tag("network", 2, 5), "A should be in network"
        assert has_tag("network", 2, 10), "B should be in network"
        assert has_tag("network", 2, 16), "C (dist 6 from B) should now be in network with radius=6"
        # D is still dist 10 from C -> still excluded
        assert not has_tag("network", 2, 26), "D (dist 10 from C) should still NOT be in network"

    def test_exact_boundary(self):
        """Junction at exactly the hop radius distance is included."""
        cfg = self._make_multi_hop_config(hop_radius=5)
        sim = Simulation(cfg)
        has_tag = _make_tag_checker_from_sim(sim, cfg)

        # B is at distance exactly 5 from A -> should be included
        assert has_tag("network", 2, 10), "On-junction at exactly hop radius should be included"


# ===========================================================================
# Recompute stability tests: on_tag_remove fires only for truly lost members
# ===========================================================================


class TestRecomputeStability:
    """Verify that recomputing a closure network only fires on_tag_remove
    for nodes that actually leave the network, not for nodes that remain
    due to redundancy.

    Strategy: use on_tag_remove("network") -> addTag("disconnected") to detect
    which objects got the handler fired. After recompute, check the "disconnected"
    tag to see which objects truly lost the network tag vs. which kept it.
    """

    def test_redundant_network_no_spurious_remove(self):
        """Diamond network: removing a bridge node doesn't fire on_tag_remove for
        nodes still reachable via the alternate path.

        Map (9x9):
            # # # # # # # # #
            # . . . . . . . #
            # . H . A . . . #   H=hub(2,2), A=breakable_junction(2,4)
            # . . . . . . . #
            # . B . C . . . #   B=junction_on(4,2), C=junction_on(4,4)
            # . . . . . . . #
            # . . . . . . . #
            # . . @ . . . . #
            # # # # # # # # #

        Network at radius=3: H -> A, H -> B, A -> C, B -> C (diamond).
        Event at t=3: remove "on" tag from A (targeted by "breakable" tag), recompute.
        C is still reachable via B. on_tag_remove should NOT fire for C or B.
        A leaves the candidate pool (no longer has "on" tag), so it loses "network".
        """
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=9, height=9, num_tokens=200),
                max_steps=20,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                agent=AgentConfig(collective="team_a"),
                objects={
                    "wall": WallConfig(tags=[typeTag("wall")]),
                    "hub": GridObjectConfig(
                        name="hub",
                        map_name="hub",
                        tags=[typeTag("hub")],
                    ),
                    "breakable_junction": GridObjectConfig(
                        name="breakable_junction",
                        map_name="breakable_junction",
                        tags=[typeTag("junction"), "on", "breakable"],
                        on_tag_remove={
                            "network": Handler(mutations=[addTag("disconnected")]),
                        },
                    ),
                    "junction_on": GridObjectConfig(
                        name="junction_on",
                        map_name="junction_on",
                        tags=[typeTag("junction"), "on"],
                        on_tag_remove={
                            "network": Handler(mutations=[addTag("disconnected")]),
                        },
                    ),
                },
                tags=["on", "network", "breakable", "disconnected"],
                collectives={
                    "team_a": CollectiveConfig(),
                },
                materialize_queries=[
                    MaterializedQuery(
                        tag="network",
                        query=ClosureQuery(
                            source=typeTag("hub"),
                            candidates=query(typeTag("junction"), [hasTag("on")]),
                            edge_filters=[maxDistance(3)],
                        ),
                    ),
                ],
                events={
                    "break_A": EventConfig(
                        name="break_A",
                        target_query=query(typeTag("junction"), [hasTag("breakable")]),
                        timesteps=[3],
                        mutations=[removeTag("on"), recomputeMaterializedQuery("network")],
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", "H", ".", "A", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", "B", ".", "C", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", "@", ".", ".", ".", ".", "#"],
                        ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name={
                        **DEFAULT_CHAR_TO_NAME,
                        "H": "hub",
                        "A": "breakable_junction",
                        "B": "junction_on",
                        "C": "junction_on",
                    },
                ),
            ),
        )

        sim = Simulation(config)
        has_tag = _make_tag_checker_from_sim(sim, config)

        # Before event: all should be in network, none disconnected
        assert has_tag("network", 2, 2), "Hub in network"
        assert has_tag("network", 2, 4), "A in network"
        assert has_tag("network", 4, 2), "B in network"
        assert has_tag("network", 4, 4), "C in network"
        assert not has_tag("disconnected", 4, 2), "B should not start disconnected"
        assert not has_tag("disconnected", 4, 4), "C should not start disconnected"

        for _ in range(4):
            sim.step()

        # After event: A lost "on" tag, so A leaves the candidate pool
        # B and C are still reachable from hub (B direct, C via B)
        assert has_tag("network", 2, 2), "Hub should still be in network"
        assert not has_tag("network", 2, 4), "A should NOT be in network (lost 'on' tag)"
        assert has_tag("network", 4, 2), "B should still be in network (direct from hub)"
        assert has_tag("network", 4, 4), "C should still be in network (via B)"

        # B and C should NOT have "disconnected" tag (on_tag_remove didn't fire)
        assert not has_tag("disconnected", 4, 2), "B should NOT have on_tag_remove fired (still in network)"
        assert not has_tag("disconnected", 4, 4), "C should NOT have on_tag_remove fired (still in network)"

        # A SHOULD have "disconnected" tag (it left the network)
        assert has_tag("disconnected", 2, 4), "A should have on_tag_remove fired (left network)"

    def test_linear_chain_break_fires_remove(self):
        """Linear chain: removing a bridge node fires on_tag_remove for
        downstream nodes that become unreachable.

        Map (11x5):
            # # # # # # # # # # #
            # . H . A . B . C . #   H=hub(1,2), A=breakable(1,4), B(1,6), C(1,8)
            # . . . . . . . . . #
            # . . . . @ . . . . #
            # # # # # # # # # # #

        Network at radius=3: H -> A -> B -> C (linear chain).
        Event at t=3: remove "on" tag from A (targeted by "breakable"), recompute.
        B and C become unreachable. on_tag_remove fires for A, B, C.
        """
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=11, height=11, num_tokens=200),
                max_steps=20,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                agent=AgentConfig(collective="team_a"),
                objects={
                    "wall": WallConfig(tags=[typeTag("wall")]),
                    "hub": GridObjectConfig(
                        name="hub",
                        map_name="hub",
                        tags=[typeTag("hub")],
                    ),
                    "breakable_junction": GridObjectConfig(
                        name="breakable_junction",
                        map_name="breakable_junction",
                        tags=[typeTag("junction"), "on", "breakable"],
                        on_tag_remove={
                            "network": Handler(mutations=[addTag("disconnected")]),
                        },
                    ),
                    "junction_on": GridObjectConfig(
                        name="junction_on",
                        map_name="junction_on",
                        tags=[typeTag("junction"), "on"],
                        on_tag_remove={
                            "network": Handler(mutations=[addTag("disconnected")]),
                        },
                    ),
                },
                tags=["on", "network", "breakable", "disconnected"],
                collectives={
                    "team_a": CollectiveConfig(),
                },
                materialize_queries=[
                    MaterializedQuery(
                        tag="network",
                        query=ClosureQuery(
                            source=typeTag("hub"),
                            candidates=query(typeTag("junction"), [hasTag("on")]),
                            edge_filters=[maxDistance(3)],
                        ),
                    ),
                ],
                events={
                    "break_A": EventConfig(
                        name="break_A",
                        target_query=query(typeTag("junction"), [hasTag("breakable")]),
                        timesteps=[3],
                        mutations=[removeTag("on"), recomputeMaterializedQuery("network")],
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
                        ["#", ".", "H", ".", "A", ".", "B", ".", "C", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", "@", ".", ".", ".", ".", "#"],
                        ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name={
                        **DEFAULT_CHAR_TO_NAME,
                        "H": "hub",
                        "A": "breakable_junction",
                        "B": "junction_on",
                        "C": "junction_on",
                    },
                ),
            ),
        )

        sim = Simulation(config)
        has_tag = _make_tag_checker_from_sim(sim, config)

        # Before event: all in network
        assert has_tag("network", 1, 2), "Hub in network"
        assert has_tag("network", 1, 4), "A in network"
        assert has_tag("network", 1, 6), "B in network"
        assert has_tag("network", 1, 8), "C in network"

        for _ in range(4):
            sim.step()

        # After event: A lost "on", B is 4 away from Hub (unreachable at radius 3)
        # so A, B, C all leave network
        assert has_tag("network", 1, 2), "Hub should still be in network"
        assert not has_tag("network", 1, 4), "A should NOT be in network"
        assert not has_tag("network", 1, 6), "B should NOT be in network (unreachable)"
        assert not has_tag("network", 1, 8), "C should NOT be in network (unreachable)"

        # on_tag_remove should have fired for A, B, C (all lost "network" tag)
        assert has_tag("disconnected", 1, 4), "A should have on_tag_remove fired"
        assert has_tag("disconnected", 1, 6), "B should have on_tag_remove fired"
        assert has_tag("disconnected", 1, 8), "C should have on_tag_remove fired"
