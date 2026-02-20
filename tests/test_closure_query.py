"""Tests for ClosureQuery Python config model and C++ integration.

Unit tests verify construction, serialization, discriminated union (AnyQuery),
use inside MaxDistanceFilter / QueryInventoryMutation, and nested queries.

Integration tests exercise the full Python config → C++ conversion → simulation
pipeline using ClosureQuery inside event filters (isNear) and mutations.
"""

from mettagrid.config.event_config import EventConfig
from mettagrid.config.filter import (
    ClosureQuery,
    HandlerTarget,
    MaxDistanceFilter,
    Query,
    TagFilter,
    hasTag,
    isA,
    isNear,
    query,
)
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
from mettagrid.config.mutation import QueryInventoryMutation, alignTo, queryDeposit
from mettagrid.config.tag import tag, typeTag
from mettagrid.map_builder.ascii import AsciiMapBuilder
from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
from mettagrid.simulator import Simulation


class TestClosureQueryConstruction:
    """Test ClosureQuery model construction."""

    def test_basic_construction(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            bridge=[isA("wire")],
            radius=1,
        )
        assert cq.query_type == "closure"
        assert cq.source == typeTag("hub")
        assert cq.radius == 1
        assert len(cq.bridge) == 1

    def test_default_radius_is_1(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            bridge=[isA("wire")],
        )
        assert cq.radius == 1

    def test_custom_radius(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            bridge=[isA("wire")],
            radius=5,
        )
        assert cq.radius == 5

    def test_with_result_filters(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            bridge=[isA("wire")],
            filters=[isA("junction")],
        )
        assert len(cq.filters) == 1
        assert len(cq.bridge) == 1

    def test_multiple_bridge_filters(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            bridge=[isA("wire"), hasTag(tag("team:red"))],
            radius=2,
        )
        assert len(cq.bridge) == 2

    def test_source_with_filters(self):
        cq = ClosureQuery(
            source=query(typeTag("hub"), [hasTag(tag("team:red"))]),
            bridge=[isA("wire")],
        )
        assert len(cq.source.filters) == 1

    def test_max_items(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            bridge=[isA("wire")],
            max_items=10,
        )
        assert cq.max_items == 10

    def test_order_by_random(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            bridge=[isA("wire")],
            order_by="random",
        )
        assert cq.order_by == "random"


class TestQueryDiscriminator:
    """Test AnyQuery discriminated union."""

    def test_query_type_tag(self):
        q = query(typeTag("hub"))
        assert q.query_type == "query"

    def test_closure_type_tag(self):
        cq = ClosureQuery(
            source=typeTag("hub"),
            bridge=[isA("wire")],
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
            bridge=[TagFilter(target=HandlerTarget.TARGET, tag=typeTag("wire"))],
            radius=3,
        )
        data = cq.model_dump()
        assert data["query_type"] == "closure"
        assert data["source"] == typeTag("hub")
        assert data["radius"] == 3
        assert len(data["bridge"]) == 1

    def test_deserialize(self):
        data = {
            "query_type": "closure",
            "source": typeTag("hub"),
            "bridge": [
                {
                    "filter_type": "tag",
                    "target": "target",
                    "tag": typeTag("wire"),
                }
            ],
            "radius": 2,
            "filters": [],
        }
        cq = ClosureQuery.model_validate(data)
        assert cq.query_type == "closure"
        assert cq.source == typeTag("hub")
        assert cq.radius == 2
        assert len(cq.bridge) == 1

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
            bridge=[isA("wire")],
            radius=2,
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
            bridge=[isA("wire")],
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
            bridge=[isA("wire")],
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
            bridge=[isA("wire")],
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
            bridge=[isA("power_line")],
            radius=1,
        )
        outer = ClosureQuery(
            source=inner,
            bridge=[isA("wire")],
            radius=2,
        )
        assert outer.query_type == "closure"
        assert outer.source.query_type == "closure"
        assert outer.source.source == typeTag("power_plant")

    def test_nested_serialization_round_trip(self):
        inner = ClosureQuery(
            source=typeTag("core"),
            bridge=[isA("conduit")],
        )
        outer = ClosureQuery(
            source=inner,
            bridge=[isA("wire")],
            filters=[isA("junction")],
        )
        data = outer.model_dump()
        restored = ClosureQuery.model_validate(data)
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
        """Junction adjacent to a hub→wire chain gets aligned via ClosureQuery.

        Map layout (7x7):
            # # # # # # #
            # . . . . . #
            # . H W . J #   H=hub, W=wire, J=junction (starts unaligned)
            # . . . . . #
            # . . @ . . #   @=agent
            # # # # # # #

        Event: align junctions near the connected network (hub + reachable wires).
        Junction at (2,5) is distance 1 from wire at (2,3)? No, distance 2.
        Let me place junction adjacent to the wire.
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
                                    bridge=[isA("wire")],
                                    radius=1,
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

        # Junction starts unaligned
        before = _count_by_collective(sim, "junction")
        assert before.get(-1, 0) == 1, "Junction should start unaligned"

        # Step past the event
        for _ in range(4):
            sim.step()

        # Junction should now be aligned to team_b (it's adjacent to wire in the network)
        team_b_id = _get_collective_id(sim, "team_b")
        after = _count_by_collective(sim, "junction")
        assert after.get(team_b_id, 0) == 1, "Junction near connected network should be aligned"

    def test_disconnected_junction_not_affected(self):
        """Junction far from the hub→wire network is NOT affected by the event.

        Map layout (9x7):
            # # # # # # # # #
            # . . . . . . . #
            # . H W J . . D #   D=disconnected junction
            # . . . . . . . #
            # . . . @ . . . #
            # # # # # # # # #

        Only the junction adjacent to the wire chain should be aligned.
        The disconnected junction at (2,7) is far from any network object.
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
                                    bridge=[isA("wire")],
                                    radius=1,
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

    def test_closure_radius_2_bridges_gap(self):
        """Closure with radius=2 bridges a gap between hub and wire.

        Map layout (9x7):
            # # # # # # # # #
            # . . . . . . . #
            # . H . W J . . #   Gap of 1 between hub(2,2) and wire(2,4), distance=2
            # . . . . . . . #
            # . . . . @ . . #
            # # # # # # # # #

        With radius=1, wire is NOT reachable from hub (distance 2).
        With radius=2, wire IS reachable, so junction adjacent to wire gets aligned.
        """

        def _make_config(closure_radius):
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
                                        bridge=[isA("wire")],
                                        radius=closure_radius,
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
        sim1 = Simulation(_make_config(closure_radius=1))
        for _ in range(4):
            sim1.step()
        after1 = _count_by_collective(sim1, "junction")
        assert after1.get(-1, 0) == 1, "With radius=1, junction should stay unaligned (wire not reachable)"

        # radius=2: wire reachable from hub, junction gets aligned
        sim2 = Simulation(_make_config(closure_radius=2))
        for _ in range(4):
            sim2.step()
        team_b_id = _get_collective_id(sim2, "team_b")
        after2 = _count_by_collective(sim2, "junction")
        assert after2.get(team_b_id, 0) == 1, "With radius=2, junction should be aligned (wire reachable)"

    def test_closure_chain_propagation(self):
        """Closure BFS propagates through a chain of wires.

        Map layout (11x7):
            # # # # # # # # # # #
            # . . . . . . . . . #
            # . H W W W W W J . #   Chain: hub → 5 wires → junction adjacent
            # . . . . . . . . . #
            # . . . . . @ . . . #
            # # # # # # # # # # #

        Closure with radius=1 should BFS through adjacent wires to reach the
        far end, making the junction (next to the last wire) a valid target.
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
                                    bridge=[isA("wire")],
                                    radius=1,
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
