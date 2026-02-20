"""Tests for the QuerySystem (MaterializedQuery + ClosureQuery).

These tests verify that:
1. Materialized queries are computed correctly via BFS from source through candidates
2. Disconnected components don't receive the materialized tag
3. Diagonal adjacency works (maxDistance(1) as edge filter)
4. No roots means no materialized tag applied
5. Edge filter radius controls hop distance in BFS
6. Multiple independent materialized queries work simultaneously
"""

from mettagrid.config.filter import HandlerTarget, TagFilter, maxDistance
from mettagrid.config.mettagrid_config import (
    GridObjectConfig,
    MettaGridConfig,
)
from mettagrid.config.query import ClosureQuery, MaterializedQuery, Query, query
from mettagrid.config.tag import typeTag
from mettagrid.simulator import Simulation


def _make_tag_checker(sim, cfg):
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


class TestBasicClosure:
    """Test basic closure tag computation via MaterializedQuery."""

    def test_hub_and_adjacent_wires_get_closure_tag(self):
        """Hub (source) + adjacent wires (candidates) should all get the closure tag."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "W", "H", "W", ".", "#"],
                ["#", ".", ".", "W", ".", ".", "#"],
                ["#", ".", ".", "@", ".", ".", "#"],
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "H": "hub", "W": "wire"},
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["hub"] = GridObjectConfig(
            name="hub",
            map_name="hub",
            tags=[typeTag("hub")],
        )
        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )

        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="connected",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("connected", 2, 3), "Hub should have 'connected' tag"
        assert has_tag("connected", 2, 2), "Wire left of hub should have 'connected' tag"
        assert has_tag("connected", 2, 4), "Wire right of hub should have 'connected' tag"
        assert has_tag("connected", 3, 3), "Wire below hub should have 'connected' tag"

    def test_disconnected_wire_not_tagged(self):
        """Wire not connected to hub should NOT get the closure tag."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "H", "W", ".", "W", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", ".", "@", ".", ".", "#"],
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "H": "hub", "W": "wire"},
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["hub"] = GridObjectConfig(
            name="hub",
            map_name="hub",
            tags=[typeTag("hub")],
        )
        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )

        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="connected",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("connected", 2, 3), "Wire next to hub should have 'connected' tag"
        assert not has_tag("connected", 2, 5), "Disconnected wire should NOT have 'connected' tag"

    def test_diagonal_adjacency(self):
        """Wire diagonally adjacent to hub should get tagged (Chebyshev distance 1)."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", "#"],
                ["#", ".", "H", ".", ".", "#"],
                ["#", ".", ".", "W", ".", "#"],
                ["#", ".", ".", ".", "@", "#"],
                ["#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "H": "hub", "W": "wire"},
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["hub"] = GridObjectConfig(
            name="hub",
            map_name="hub",
            tags=[typeTag("hub")],
        )
        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )

        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="connected",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("connected", 2, 2), "Hub should have 'connected' tag"
        assert has_tag("connected", 3, 3), "Diagonally adjacent wire should have 'connected' tag"

    def test_no_roots_no_closure_tag(self):
        """If no objects match root config, no closure tag should be applied."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "W", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "W": "wire"},
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )

        cfg.game.tags = [typeTag("hub")]
        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="connected",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert not has_tag("connected", 2, 2), "Wire should NOT have 'connected' tag without any hub"


class TestAdvancedClosure:
    """Test advanced closure tag features."""

    def test_edge_filter_radius_controls_hop_distance(self):
        """maxDistance radius in edge_filters controls how far BFS expands per hop.

        Map: H . W (hub at (2,2), empty at (2,3), wire at (2,4))
        radius=1: wire is at Chebyshev distance 2 from hub — unreachable in 1 hop
        radius=2: wire is within reach — hub can reach wire directly
        """
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "H", ".", "W", ".", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", ".", "@", ".", ".", "#"],
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "H": "hub", "W": "wire"},
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["hub"] = GridObjectConfig(
            name="hub",
            map_name="hub",
            tags=[typeTag("hub")],
        )
        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )

        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="r1",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
            MaterializedQuery(
                tag="r2",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(2)],
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        # radius=1: wire is 2 cells away, beyond the 1-cell hop distance
        assert has_tag("r1", 2, 2), "Hub should have 'r1' tag"
        assert not has_tag("r1", 2, 4), "Wire at distance 2 should NOT have 'r1' tag (radius=1)"

        # radius=2: wire is within the 2-cell hop distance
        assert has_tag("r2", 2, 2), "Hub should have 'r2' tag"
        assert has_tag("r2", 2, 4), "Wire at distance 2 should have 'r2' tag (radius=2)"

    def test_adjacent_chain_with_radius_1(self):
        """Adjacent candidates chain indefinitely with maxDistance(1).

        Map: H W W — hub expands to wire1, then wire1 expands to wire2.
        """
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "H", "W", "W", ".", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", ".", "@", ".", ".", "#"],
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "H": "hub", "W": "wire"},
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["hub"] = GridObjectConfig(
            name="hub",
            map_name="hub",
            tags=[typeTag("hub")],
        )
        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )

        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="net",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("net", 2, 2), "Hub should have 'net' tag"
        assert has_tag("net", 2, 3), "Adjacent wire should have 'net' tag"
        assert has_tag("net", 2, 4), "Chained wire should have 'net' tag (adjacent to first wire)"

    def test_max_distance_zero_is_unlimited(self):
        """maxDistance(0) means unlimited range — all candidates are reachable.

        Map: H . . . W  (hub at (2,2), wire at (2,6) — distance 4)
        radius=1: wire is far beyond 1 hop — NOT reachable
        radius=0: unlimited — wire IS reachable regardless of distance
        """
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "H", ".", ".", ".", "W", ".", "#"],
                ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                ["#", ".", ".", ".", "@", ".", ".", ".", "#"],
                ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "H": "hub", "W": "wire"},
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["hub"] = GridObjectConfig(
            name="hub",
            map_name="hub",
            tags=[typeTag("hub")],
        )
        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )

        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="limited",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
            MaterializedQuery(
                tag="unlimited",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(0)],
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert not has_tag("limited", 2, 6), "Wire at distance 4 should NOT have 'limited' tag (radius=1)"
        assert has_tag("unlimited", 2, 2), "Hub should have 'unlimited' tag"
        assert has_tag("unlimited", 2, 6), "Wire at distance 4 should have 'unlimited' tag (radius=0 = unlimited)"

    def test_multiple_closures(self):
        """Two independent MaterializedQuery entries should work simultaneously."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "H", "W", ".", ".", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", ".", "P", "C", ".", "#"],
                ["#", ".", ".", "@", ".", ".", "#"],
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={
                "#": "wall",
                "@": "agent.agent",
                ".": "empty",
                "H": "hub",
                "W": "wire",
                "P": "power",
                "C": "cable",
            },
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["hub"] = GridObjectConfig(
            name="hub",
            map_name="hub",
            tags=[typeTag("hub")],
        )
        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )
        cfg.game.objects["power"] = GridObjectConfig(
            name="power",
            map_name="power",
            tags=[typeTag("power")],
        )
        cfg.game.objects["cable"] = GridObjectConfig(
            name="cable",
            map_name="cable",
            tags=[typeTag("cable")],
        )

        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="net1",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
            MaterializedQuery(
                tag="net2",
                query=ClosureQuery(
                    source=typeTag("power"),
                    candidates=query(typeTag("cable")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("net1", 2, 2), "Hub should have 'net1' tag"
        assert has_tag("net1", 2, 3), "Wire should have 'net1' tag"
        assert not has_tag("net1", 4, 3), "Power should NOT have 'net1' tag"
        assert not has_tag("net1", 4, 4), "Cable should NOT have 'net1' tag"

        assert has_tag("net2", 4, 3), "Power should have 'net2' tag"
        assert has_tag("net2", 4, 4), "Cable should have 'net2' tag"
        assert not has_tag("net2", 2, 2), "Hub should NOT have 'net2' tag"
        assert not has_tag("net2", 2, 3), "Wire should NOT have 'net2' tag"


class TestNestedQueryConstraints:
    """Outer query constraints must be preserved when source is a sub-query."""

    def _make_alpha_beta_config(self):
        """Two object types sharing a 'selectable' tag on a small grid."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "A", ".", "B", ".", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", ".", "@", ".", ".", "#"],
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "A": "alpha", "B": "beta"},
        )
        cfg.game.actions.noop.enabled = True
        cfg.game.tags = ["selectable"]

        cfg.game.objects["alpha"] = GridObjectConfig(
            name="alpha",
            map_name="alpha",
            tags=[typeTag("alpha"), "selectable"],
        )
        cfg.game.objects["beta"] = GridObjectConfig(
            name="beta",
            map_name="beta",
            tags=[typeTag("beta"), "selectable"],
        )
        return cfg

    def test_nested_query_filters_applied(self):
        """query(inner_query, filters=[...]) must apply the outer filters."""
        cfg = self._make_alpha_beta_config()
        inner = Query(source="selectable")
        outer = Query(
            source=inner,
            filters=[TagFilter(target=HandlerTarget.TARGET, tag=typeTag("alpha"))],
        )
        cfg.game.materialize_queries = [
            MaterializedQuery(tag="chosen", query=outer),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("chosen", 2, 2), "Alpha should have 'chosen' tag"
        assert not has_tag("chosen", 2, 4), "Beta should NOT have 'chosen' (outer filter requires type:alpha)"

    def test_nested_query_max_items_applied(self):
        """query(inner_query, max_items=N) must limit results to N."""
        cfg = self._make_alpha_beta_config()
        inner = Query(source="selectable")
        outer = Query(source=inner, max_items=1)
        cfg.game.materialize_queries = [
            MaterializedQuery(tag="chosen", query=outer),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        tagged_count = sum(1 for r, c in [(2, 2), (2, 4)] if has_tag("chosen", r, c))
        assert tagged_count == 1, f"max_items=1 should tag exactly 1 object, got {tagged_count}"
